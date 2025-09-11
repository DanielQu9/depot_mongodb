from datetime import datetime, date
from typing import Literal, Any, Iterator
from pymongo import MongoClient, AsyncMongoClient
import json


class DepotItem:
    """
    模塊化紀錄倉庫進出\n
    """

    def __init__(
        self,
        type: Literal["in", "out", "auto", "set"],
        item: str,
        amount: int,
        time=None,
    ) -> None:
        """
        type: 'in' or 'out' or 'auto'(自動辨識正負數) or 'set'(設置數量, 跳過檢查)\n
        item: 商品名稱\n
        amount: 數量（正整數）\n
        time: 時間（可選，預設為現在時間）\n
        """

        # 格式驗證
        if type != "set":
            if type == "auto":
                if amount <= 0:
                    type = "out"
                    amount *= -1
                else:
                    type = "in"
            elif type not in ("in", "out"):
                raise DepotError(
                    "警告: type 必須是 'in' 或 'out' 或 'set'，已忽略此筆。", "type"
                )

            if not isinstance(amount, int) or amount <= 0:
                raise DepotError("警告: amount 必須是正整數，已忽略此筆。", "amount")
        if time is None:
            time = datetime.now()

        self.type: Literal["in", "out", "set"] = type
        self.item: str = item
        self.amount: int = amount
        self.time: datetime = time

    def __iter__(self) -> Any:
        return iter((self.type, self.item, self.amount, self.time))


class DepotError(Exception):
    """depot.py 報錯格式"""

    def __init__(self, message: str, field: str | None = None):
        self.message = message
        self.field = field
        super().__init__(f"{message} (欄位：{field})" if field else message)


class Depot:
    """
    倉庫紀錄\n
    - write 將紀錄寫入資料庫\n
    - show_inventory 打印當前倉庫\n
    - get_inventory 輸出當前倉庫\n
    - in_inventory 該資料是否存在\n
    - set_tag 設定tag標籤\n
    - get_tag_json 取得該物品的tag頁\n
    - find_records 依據日期尋找資料表\n
    - date_collections 獲取所有非 inventory 的子資料表\n
    \n
    使用範例: \n
      from depot import Depot, DepotItem

      db = Depot()
      item = DepotItem("in", "物品", 1)
      db.write(item)

    \n
    設定: \n
    - 可設定 Depot.remove_on_zero 進行移除等於零的欄位\n
    """

    def __init__(self) -> None:
        # 連線
        self.client = MongoClient("mongodb://localhost:27017/")
        self.db = self.client["depotDB"]

        # 資料表
        self.inventory = self.db["inventory"]  # 倉庫
        self.collection = self.__today_collection  # 當日交易紀錄

        self.remove_on_zero: bool = False  # 是否清除已歸零的倉位

        # 添加預設資料
        self.__init_default_items()

    def write(self, DItem: DepotItem, source: str = "local") -> None:
        """新增一筆進出貨資料"""
        self.__write_to_db(*DItem, source=source)

    def get_inventory(self) -> dict[str, int] | None:
        """
        輸出當前倉庫內容\n
        建議使用 dict.items() 獲取物品和數量\n
        範例:\n
         inventory = Depot.get_inventory()\n
         if inventory is None:
            ...
         else:
            for name, amount in inventory.items():
                print(name, amount)
        """
        Doc = list(self.inventory.find())
        if Doc == []:
            return None
        else:
            return {items["item"]: items.get("amount", -32768) for items in Doc}

    def show_inventory(self) -> None:
        """打印當前庫存內容"""
        print("倉庫現況：")
        Doc = self.get_inventory()

        if Doc != None:
            for item, amount in Doc.items():
                print(f"    {item}: {amount} 件")
        else:
            print(f"    倉庫為空")

    def __write_to_db(
        self,
        type: Literal["in", "out", "set"],
        item: str,
        amount: int,
        time: datetime,
        source: str,
    ) -> None:
        # 重新獲取日期
        self.collection = self.__today_collection

        # 取得現有庫存
        item_doc = self.inventory.find_one({"item": item})
        current_amount = item_doc["amount"] if item_doc else 0

        if type == "in":
            new_amount = current_amount + amount
        elif type == "out":
            if current_amount < amount:
                raise DepotError(
                    f"警告: 紀錄目標 {item} 為負數，當前: {current_amount}，目標: {current_amount - amount}，已忽略此筆。"
                )
            else:
                new_amount = current_amount - amount
        elif type == "set":
            new_amount = amount

        # 更新或新增庫存
        self.inventory.update_one(
            {"item": item},
            {"$set": {"amount": new_amount}, "$setOnInsert": {"tag": {}}},
            upsert=True,
        )

        # 寫入當天的紀錄表
        record = {
            "type": type,
            "item": item,
            "amount": amount,
            "time": time,
            "source": source,
        }
        result = self.collection.insert_one(record)
        print(f"紀錄 [{type}] {item}*{amount} 成功，紀錄 ID: {result.inserted_id}")

        # 刪除歸零倉庫位
        if self.remove_on_zero:
            self.inventory.delete_one(
                {
                    "item": item,
                    "amount": 0,
                    "$or": [
                        {"tag.no_auto_remove": {"$ne": True}},
                        {"tag.no_auto_remove": {"$exists": False}},
                    ],
                }
            )
            print(f"移除 空物品 {item} 成功")

    def set_tag(self, item: str, tag: dict[str, Any]) -> None:
        """
        為倉庫資料插入tag屬性\n
        item: 物品名稱\n
        tag: 插入標籤\n
        """
        data = self.inventory.find_one({"item": item})
        if data == None:
            print(f"警告: 倉庫內未找到 {item} 請確認已添加物品，已忽略此筆。")
            return None

        self.inventory.update_one({"item": item}, {"$set": {f"tag": tag}}, upsert=True)

    def get_tag_json(self, item: str) -> dict[str, Any] | None:
        """
        返回tag表\n
        item: 物品名稱\n
        """
        data = self.inventory.find_one({"item": item})
        if data == None:
            print(f"警告: 倉庫內未找到 {item} 請確認已添加物品，已忽略此筆。")
            return None

        return dict(data).get("tag", {})

    def in_inventory(self, item: str) -> bool:
        """
        檢查該物品是否存在於倉庫內\n
        item: 物品名稱\n
        """
        if self.inventory.find_one({"item": item}) is None:
            print(f"警告: 倉庫內未找到 {item} 請確認已添加物品，已忽略此筆。")
            return False
        return True

    def find_records(self, date: str) -> list | None:
        """
        依據日期找資料表, 並回傳其紀錄\n
        date: 格式為 YYYY-MM-DD
        """

        if date not in self.date_collections:
            return None
        return list(self.db[date].find())

    @property
    def __today_collection(self):
        """當日資料表"""
        return self.db[f"{date.today()}"]

    @property
    def date_collections(self) -> list[str]:
        """獲取所有非 inventory 的子資料表"""
        return [i for i in self.db.list_collection_names() if i != "inventory"]

    def __init_default_items(self):
        """配合esp, 給資料庫插入三組預設物品"""
        j = json.load(open("./config/item_id.json"))
        lst = [j[i]["name"] for i in range(len(j))]
        for i in range(len(lst)):
            self.inventory.update_one(
                {"item": j[i]["name"]},
                {
                    # "$setOnInsert": {
                    #     "amount": 0,
                    # },
                    "$set": {
                        "amount": 0,
                        "tag": {
                            "no_auto_remove": j[i]["tag"]["no_auto_remove"],
                            "unit_weight": j[i]["unit_weight"],
                            "min_weight_warning": j[i]["min_weight_warning"],
                        },
                    },
                },
                upsert=True,
            )


class AsyncDepot:
    """
    非同步-倉庫紀錄\n
    - write 將紀錄寫入資料庫\n
    - get_inventory 輸出當前倉庫\n
    - set_tag 設定tag標籤\n
    - get_tag_json 取得該物品的tag頁\n
    - find_records 依據日期尋找資料表\n
    - date_collections 獲取所有非 inventory 的子資料表\n
    \n
    使用範例:\n

      from depot import AsyncDepot, DepotItem
      import asyncio

      async def main():
        db = AsyncDepot()
        item = DepotItem("in", "物品", 1)
        await db.write(item)

      asyncio.run(main())

    \n
    設定: \n
    - 可設定 Depot.remove_on_zero 進行移除等於零的欄位\n
    """

    def __init__(self) -> None:
        # 連線
        self.client = AsyncMongoClient("mongodb://localhost:27017/")
        self.db = self.client["depotDB"]

        # 資料表
        self.inventory = self.db["inventory"]  # 倉庫
        self.collection = self.db[f"{date.today()}"]  # 交易紀錄

        self.remove_on_zero: bool = False  # 是否清除已歸零的倉位

        # 添加預設資料
        sync_depot = Depot()
        sync_depot._Depot__init_default_items()  # type: ignore

    async def write(self, DItem: DepotItem, source: str = "local") -> None:
        """新增一筆進出貨資料"""

        # 重新獲取日期
        self.collection = self.db[f"{date.today()}"]

        # 解包資料
        type: Literal["in", "out", "set"] = DItem.type
        item: str = DItem.item
        amount: int = DItem.amount
        time: datetime = DItem.time

        # 取得現有庫存
        item_doc = await self.inventory.find_one({"item": item})
        current_amount = item_doc["amount"] if item_doc else 0

        if type == "in":
            new_amount = current_amount + amount
        elif type == "out":
            if current_amount < amount:
                raise DepotError(
                    f"警告: 紀錄目標 {item} 為負數，當前: {current_amount}，目標: {current_amount - amount}，已忽略此筆。"
                )
            else:
                new_amount = current_amount - amount
        elif type == "set":
            new_amount = amount

        # 更新或新增庫存
        await self.inventory.update_one(
            {"item": item},
            {"$set": {"amount": new_amount}, "$setOnInsert": {"tag": {}}},
            upsert=True,
        )

        # 寫入當天的紀錄表
        record = {
            "type": type,
            "item": item,
            "amount": amount,
            "time": time,
            "source": source,
        }
        result = await self.collection.insert_one(record)
        print(f"紀錄 [{type}] {item}*{amount} 成功，紀錄 ID: {result.inserted_id}")

        # 刪除歸零倉庫位
        if self.remove_on_zero:
            await self.inventory.delete_one(
                {
                    "item": item,
                    "amount": 0,
                    "$or": [
                        {"tag.no_auto_remove": {"$ne": True}},
                        {"tag.no_auto_remove": {"$exists": False}},
                    ],
                }
            )
            print(f"移除 空物品 {item} 成功")

    async def get_inventory(self) -> dict[str, int]:
        """
        輸出當前倉庫內容\n
        建議使用 dict.items() 獲取物品和數量\n
        範例:\n
         async def main():
           db = AsyncDepot()
           inventory = await db.get_inventory()
           for name, amount in inventory.items():
             print(name, amount)
        """
        return {
            items["item"]: items.get("amount", -32768)
            async for items in self.inventory.find()
        }

    async def set_tag(self, item: str, tag: dict[str, Any]) -> None:
        """
        為倉庫資料插入tag屬性\n
        item: 物品名稱\n
        tag: 插入標籤\n
        """
        data = await self.inventory.find_one({"item": item})
        if data is None:
            raise DepotError(
                f"警告: 倉庫內未找到 {item} 請確認已添加物品，已忽略此筆。"
            )

        await self.inventory.update_one(
            {"item": item}, {"$set": {f"tag": tag}}, upsert=True
        )

    async def get_tag_json(self, item: str) -> dict[str, Any] | None:
        """
        返回tag表\n
        item: 物品名稱\n
        """
        data = await self.inventory.find_one({"item": item})
        if data is None:
            raise DepotError(
                f"警告: 倉庫內未找到 {item} 請確認已添加物品，已忽略此筆。"
            )

        return dict(data).get("tag", {})

    async def find_records(self, date: str) -> list[Any] | None:
        """
        依據日期找資料表, 並回傳其紀錄\n
        date: 格式為 YYYY-MM-DD
        """
        if date not in await self.date_collections:
            return None
        return [i async for i in self.db[date].find()]

    @property
    async def date_collections(self) -> list[str]:
        """獲取所有非 inventory 的子資料表"""
        return [i for i in await self.db.list_collection_names() if i != "inventory"]


if __name__ == "__main__":
    depot = Depot()
