from datetime import datetime, date
from typing import Literal, Any, Iterator
from pymongo import MongoClient, AsyncMongoClient
import json
import logging
import sys

MONGO_ADDR = "mongodb://localhost:27017/"

# 全局設定
ENABLE_COLORS = True  # 設置為 False 可關閉顏色輸出


def set_color_mode(enabled: bool) -> None:
    """
    動態設置顏色輸出模式

    Args:
        enabled: True 啟用顏色輸出，False 關閉顏色輸出
    """
    global ENABLE_COLORS
    ENABLE_COLORS = enabled
    status = "啟用" if enabled else "關閉"
    _log_operation("INFO", "顏色輸出模式", f"已{status}顏色輸出")


# 設置日誌配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

# 創建專用的 logger
depot_logger = logging.getLogger("depot")


# ANSI 顏色代碼
class Colors:
    """ANSI 顏色代碼常數"""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # 前景色
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # 亮色
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"

    # 背景色
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"


def _log_operation(
    level: str,
    operation: str,
    details: str = "",
    item: str = "",
    amount: int | None = None,
):
    """
    統一的日誌輸出函數（帶顏色支持）

    Args:
        level: 日誌等級 ('INFO', 'WARNING', 'ERROR', 'SUCCESS')
        operation: 操作類型
        details: 詳細信息
        item: 物品名稱
        amount: 數量
    """
    # 根據等級選擇顏色和前綴
    if ENABLE_COLORS:
        if level == "SUCCESS":
            color = Colors.BRIGHT_GREEN
            prefix = f"{Colors.BOLD}SUCCESS{Colors.RESET} {color}[成功]{Colors.RESET}"
        elif level == "WARNING":
            color = Colors.BRIGHT_YELLOW
            prefix = f"{Colors.BOLD}WARNING{Colors.RESET} {color}[警告]{Colors.RESET}"
        elif level == "ERROR":
            color = Colors.BRIGHT_RED
            prefix = f"{Colors.BOLD}ERROR{Colors.RESET} {color}[錯誤]{Colors.RESET}"
        else:
            color = Colors.BRIGHT_CYAN
            prefix = f"{Colors.BOLD}INFO{Colors.RESET} {color}[資訊]{Colors.RESET}"

        # 構建彩色消息
        message = f"{prefix} {Colors.WHITE}{operation}{Colors.RESET}"

        if item:
            message += f" - {Colors.BRIGHT_BLUE}物品:{Colors.RESET} {Colors.CYAN}{item}{Colors.RESET}"
        if amount is not None:
            message += f" - {Colors.BRIGHT_BLUE}數量:{Colors.RESET} {Colors.MAGENTA}{amount}{Colors.RESET}"
        if details:
            message += f" - {Colors.DIM}{details}{Colors.RESET}"

        # 輸出彩色日誌
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        colored_message = f"{Colors.DIM}{timestamp}{Colors.RESET} - {Colors.BOLD}depot{Colors.RESET} - {message}"
        print(colored_message)
    else:
        # 無顏色版本（回退到原始格式）
        if level == "SUCCESS":
            message = f"[成功] {operation}"
        elif level == "WARNING":
            message = f"[警告] {operation}"
        elif level == "ERROR":
            message = f"[錯誤] {operation}"
        else:
            message = f"[資訊] {operation}"

        if item:
            message += f" - 物品: {item}"
        if amount is not None:
            message += f" - 數量: {amount}"
        if details:
            message += f" - {details}"

        # 使用標準 logger
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        plain_message = f"{timestamp} - depot - {message}"
        print(plain_message)


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

        # 輸出彩色錯誤日誌
        if field:
            _log_operation("ERROR", "DepotError 異常", f"欄位: {field}", message)
            error_msg = f"{message} (欄位：{field})"
        else:
            _log_operation("ERROR", "DepotError 異常", "", message)
            error_msg = message

        super().__init__(error_msg)


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

        # 初始化工具類別
        self.tool = self.Tool(self)

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
        _log_operation("INFO", "查詢倉庫現況")
        Doc = self.get_inventory()

        if Doc != None:
            for item, amount in Doc.items():
                _log_operation("INFO", "庫存項目", f"{amount} 件", item, amount)
        else:
            _log_operation("INFO", "倉庫狀態", "倉庫為空")

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
        _log_operation(
            "SUCCESS",
            f"倉庫{type}庫操作",
            f"紀錄 ID: {result.inserted_id}",
            item,
            amount,
        )

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
            _log_operation("SUCCESS", "自動移除空物品", "", item)

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
            _log_operation(
                "WARNING", "設置標籤失敗", "倉庫內未找到物品，請確認已添加物品", item
            )
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
            _log_operation(
                "WARNING", "獲取標籤失敗", "倉庫內未找到物品，請確認已添加物品", item
            )
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
            _log_operation(
                "WARNING", "檢查物品存在性", "倉庫內未找到物品，請確認已添加物品", item
            )
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

    class Tool:
        """
        倉庫管理工具類別

        提供額外的倉庫管理功能，如清空倉庫等操作
        """

        def __init__(self, parent_depot: "Depot") -> None:
            """
            初始化工具類別

            Args:
                parent_depot: 父級 Depot 實例
            """
            self.parent = parent_depot
            self.client = parent_depot.client
            self.db = parent_depot.db
            self.inventory = parent_depot.inventory

        def clear_inventory(self, double_check: bool) -> bool:
            """
            清空 inventory 資料表

            Args:
                double_check: 安全確認，必須為 True 才會執行清空操作

            Returns:
                bool: 操作是否成功
            """
            if not double_check:
                _log_operation(
                    "WARNING",
                    "清空倉庫操作",
                    "double_check 參數必須為 True 才能執行清空操作",
                )
                return False

            try:
                # 刪除 inventory 資料表中的所有文件
                result = self.inventory.delete_many({})
                _log_operation(
                    "SUCCESS", "清空倉庫", f"共刪除 {result.deleted_count} 筆資料"
                )
                self.parent.__init__()
                return True
            except Exception as e:
                _log_operation("ERROR", "清空倉庫失敗", str(e))
                return False


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

        # 初始化工具類別
        self.tool = self.Tool(self)

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
        operation_type: Literal["in", "out", "set"] = DItem.type
        item: str = DItem.item
        amount: int = DItem.amount
        time: datetime = DItem.time

        # 取得現有庫存
        item_doc = await self.inventory.find_one({"item": item})
        current_amount = item_doc["amount"] if item_doc else 0

        if operation_type == "in":
            new_amount = current_amount + amount
        elif operation_type == "out":
            if current_amount < amount:
                raise DepotError(
                    f"警告: 紀錄目標 {item} 為負數，當前: {current_amount}，目標: {current_amount - amount}，已忽略此筆。"
                )
            else:
                new_amount = current_amount - amount
        elif operation_type == "set":
            new_amount = amount

        # 更新或新增庫存
        await self.inventory.update_one(
            {"item": item},
            {"$set": {"amount": new_amount}, "$setOnInsert": {"tag": {}}},
            upsert=True,
        )

        # 寫入當天的紀錄表
        record = {
            "type": operation_type,
            "item": item,
            "amount": amount,
            "time": time,
            "source": source,
        }
        result = await self.collection.insert_one(record)
        _log_operation(
            "SUCCESS",
            f"倉庫{operation_type}庫操作",
            f"紀錄 ID: {result.inserted_id}",
            item,
            amount,
        )

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
            _log_operation("SUCCESS", "自動移除空物品", "", item)

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
        """
        非同步倉庫管理工具類別

        提供額外的非同步倉庫管理功能，如清空倉庫等操作
        """

        def __init__(self, parent_depot: "AsyncDepot") -> None:
            """
            初始化工具類別

            Args:
                parent_depot: 父級 AsyncDepot 實例
            """
            self.parent = parent_depot
            self.client = parent_depot.client
            self.db = parent_depot.db
            self.inventory = parent_depot.inventory

        async def clear_inventory(self, double_check: bool) -> bool:
            """
            清空 inventory 資料表（非同步版本）

            Args:
                double_check: 安全確認，必須為 True 才會執行清空操作

            Returns:
                bool: 操作是否成功
            """
            if not double_check:
                _log_operation(
                    "WARNING",
                    "清空倉庫操作",
                    "double_check 參數必須為 True 才能執行清空操作",
                )
                return False

            try:
                # 刪除 inventory 資料表中的所有文件
                result = await self.inventory.delete_many({})
                _log_operation(
                    "SUCCESS", "清空倉庫", f"共刪除 {result.deleted_count} 筆資料"
                )
                self.parent.__init__()
                return True
            except Exception as e:
                _log_operation("ERROR", "清空倉庫失敗", str(e))
                return False


if __name__ == "__main__":
    depot = Depot()
