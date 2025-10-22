from datetime import datetime, date
from typing import Literal, Any, Iterator
from pymongo import MongoClient, AsyncMongoClient
import json

MONGO_ADDR = "mongodb://localhost:27017/"


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
        初始化倉庫項目

        Args:
            type: 操作類型 - 'in'(入庫) / 'out'(出庫) / 'auto'(自動辨識正負數) / 'set'(設置數量, 跳過檢查)
            item: 商品名稱
            amount: 數量（正整數）
            time: 時間（可選，預設為現在時間）
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
        self.client = MongoClient(MONGO_ADDR)
        self.db = self.client["depotDB"]

        # 資料表
        self.inventory = self.db["inventory"]  # 倉庫
        self.collection = self.__today_collection  # 當日交易紀錄

        self.remove_on_zero: bool = False  # 是否清除已歸零的倉位

        # 添加預設資料
        self.__init_default_items()

    def write(self, DItem: DepotItem, source: str = "local") -> None:
        """
        新增一筆進出貨資料

        Args:
            DItem: DepotItem 實例，包含操作詳細資訊
            source: 資料來源標識，預設為 "local"
        """
        if not isinstance(DItem, DepotItem):
            raise DepotError(
                f"警告: DItem 必須是 DepotItem 實例，接收到 {type(DItem).__name__}",
                "DItem",
            )

        self.__write_to_db(*DItem, source=source)

    def get_inventory(self) -> dict[str, int] | None:
        """
        輸出當前倉庫內容

        Returns:
            dict[str, int] | None: 物品名稱與數量的字典，如果倉庫為空則返回 None

        範例:\n
          inventory = depot.get_inventory()
          if inventory is not None:
           for name, amount in inventory.items():
            print(name, amount)
        """
        Doc = list(self.inventory.find())
        if Doc == []:
            return None
        else:
            return {items["item"]: items.get("amount", -32768) for items in Doc}

    def show_inventory(self) -> None:
        """
        打印當前庫存內容到控制台

        Note:
            直接輸出格式化的庫存資訊，無返回值
        """
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
        為倉庫資料插入 tag 屬性

        Args:
            item: 物品名稱
            tag: 插入的標籤字典

        Note:
            如果物品不存在於倉庫中，將輸出警告訊息
        """
        data = self.inventory.find_one({"item": item})
        if data == None:
            print(f"警告: 倉庫內未找到 {item} 請確認已添加物品，已忽略此筆。")
            return None

        self.inventory.update_one({"item": item}, {"$set": {f"tag": tag}}, upsert=True)

    def get_tag_json(self, item: str) -> dict[str, Any] | None:
        """
        返回指定物品的 tag 標籤資料

        Args:
            item: 物品名稱

        Returns:
            dict[str, Any] | None: 標籤字典，如果物品不存在則返回 None
        """
        data = self.inventory.find_one({"item": item})
        if data == None:
            print(f"警告: 倉庫內未找到 {item} 請確認已添加物品，已忽略此筆。")
            return None

        return dict(data).get("tag", {})

    def in_inventory(self, item: str) -> bool:
        """
        檢查該物品是否存在於倉庫內

        Args:
            item: 物品名稱

        Returns:
            bool: 物品是否存在於倉庫中
        """
        if self.inventory.find_one({"item": item}) is None:
            print(f"警告: 倉庫內未找到 {item} 請確認已添加物品，已忽略此筆。")
            return False
        return True

    def find_records(self, date: str) -> list | None:
        """
        依據日期尋找資料表並回傳其紀錄

        Args:
            date: 日期字串，格式為 YYYY-MM-DD

        Returns:
            list | None: 該日期的紀錄列表，如果不存在則返回 None
        """

        if date not in self.date_collections:
            return None
        return list(self.db[date].find())

    @property
    def __today_collection(self):
        """
        當日資料表

        Returns:
            Collection: 當前日期對應的 MongoDB 集合
        """
        return self.db[f"{date.today()}"]

    @property
    def date_collections(self) -> list[str]:
        """
        獲取所有非 inventory 的子資料表

        Returns:
            list[str]: 日期格式的資料表名稱列表
        """
        return [i for i in self.db.list_collection_names() if i != "inventory"]

    def __init_default_items(self):
        """
        配合 ESP 設備，給資料庫插入預設物品

        Note:
            從 config/item_id.json 讀取配置並初始化預設物品至資料庫
        """
        j: dict = json.load(open("./config/item_id.json", encoding="utf-8"))
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
                            "no_auto_remove": j[i]["setting"].get(
                                "no_auto_remove", False
                            ),
                            "unit_weight": j[i]["setting"].get("unit_weight", 0),
                            "min_weight_warning": j[i]["setting"].get(
                                "min_weight_warning", 0
                            ),
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
        self.client = AsyncMongoClient(MONGO_ADDR)
        self.db = self.client["depotDB"]

        # 資料表
        self.inventory = self.db["inventory"]  # 倉庫
        self.collection = self.db[f"{date.today()}"]  # 交易紀錄

        self.remove_on_zero: bool = False  # 是否清除已歸零的倉位

        # 添加預設資料
        sync_depot = Depot()
        sync_depot._Depot__init_default_items()  # type: ignore

    async def write(self, DItem: DepotItem, source: str = "local") -> None:
        """
        新增一筆進出貨資料（非同步版本）

        Args:
            DItem: DepotItem 實例，包含操作詳細資訊
            source: 資料來源標識，預設為 "local"
        """
        if not isinstance(DItem, DepotItem):
            raise DepotError(
                f"警告: DItem 必須是 DepotItem 實例，接收到 {type(DItem).__name__}",
                "DItem",
            )

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
        輸出當前倉庫內容（非同步版本）

        Returns:
            dict[str, int]: 物品名稱與數量的字典

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
        為倉庫資料插入 tag 屬性（非同步版本）

        Args:
            item: 物品名稱
            tag: 插入的標籤字典

        Raises:
            DepotError: 如果物品不存在於倉庫中
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
        返回指定物品的 tag 標籤資料（非同步版本）

        Args:
            item: 物品名稱

        Returns:
            dict[str, Any] | None: 標籤字典

        Raises:
            DepotError: 如果物品不存在於倉庫中
        """
        data = await self.inventory.find_one({"item": item})
        if data is None:
            raise DepotError(
                f"警告: 倉庫內未找到 {item} 請確認已添加物品，已忽略此筆。"
            )

        return dict(data).get("tag", {})

    async def find_records(self, date: str) -> list[Any] | None:
        """
        依據日期尋找資料表並回傳其紀錄（非同步版本）

        Args:
            date: 日期字串，格式為 YYYY-MM-DD

        Returns:
            list[Any] | None: 該日期的紀錄列表，如果不存在則返回 None
        """
        if date not in await self.date_collections:
            return None
        return [i async for i in self.db[date].find()]

    @property
    async def date_collections(self) -> list[str]:
        """
        獲取所有非 inventory 的子資料表（非同步版本）

        Returns:
            list[str]: 日期格式的資料表名稱列表
        """
        return [i for i in await self.db.list_collection_names() if i != "inventory"]


class Tool:
    def __init__(self) -> None:
        # 連線
        self.client = MongoClient(MONGO_ADDR)
        self.db = self.client["depotDB"]

        # 資料表
        self.inventory = self.db["inventory"]  # 倉庫

    def clear_inventory(self, double_check: bool) -> bool:
        """
        清空 inventory 資料表

        Args:
            double_check (bool): 安全確認，必須為 True 才會執行清空操作

        Returns:
            bool: 操作是否成功
        """
        if not double_check:
            print("警告: double_check 參數必須為 True 才能執行清空操作")
            return False

        try:
            # 刪除 inventory 資料表中的所有文件
            result = self.inventory.delete_many({})
            print(f"成功清空 inventory 資料表，共刪除 {result.deleted_count} 筆資料")
            return True
        except Exception as e:
            print(f"清空 inventory 資料表時發生錯誤: {e}")
            return False


if __name__ == "__main__":
    depot = Depot()
