import datetime
from typing import Literal
from pymongo import MongoClient


class Depot:
    """
    倉庫紀錄\n
    - write 將紀錄寫入資料庫\n
    - show_inventory 打印當前倉庫\n
    - get_inventory 輸出當前倉庫\n
    - seed_keep 寄送已打包的紀錄\n
    
    檢視已打包資料: print(Depot.keep_list)
    """
    def __init__(self) -> None:
        # 連線
        self.client = MongoClient("mongodb://localhost:27017/")
        self.db = self.client["depotDB"]
        
        # 資料表
        self.inventory = self.db["inventory"]       # 倉庫
        self.collection = self.__today_collection   # 交易紀錄
        
        self.keep_list: list = []
        
    def write(self,
              type: Literal["in", "out"],
              item: str,
              amount: int,
              keep: bool=False,
              time=None
    ) -> None:
        """
        新增一筆進出貨資料\n
        type: 'in' or 'out'\n
        item: 商品名稱\n
        amount: 數量（正整數）\n
        keep: 是/否 將打包後寫入\n
        time: 時間（可選，預設為現在時間）\n
        """
        
        if type not in ("in", "out"):
            print("警告: type 必須是 'in' 或 'out'，已忽略此筆。")
            return None
        if not isinstance(amount, int) or amount <= 0:
            print("警告: amount 必須是正整數，已忽略此筆。")
            return None
        if time is None:
            time = datetime.datetime.now()

        if keep:
            self.keep_list.append((type, item, amount, time))
        else:
            self.__write_to_db(type, item, amount, time)
    
    def get_inventory(self) -> (dict[str, int] | None):
        """
        輸出當前倉庫內容\n
        
        範例:  {"物品[str]": "數量[int]"}
        """
        Doc = self.inventory.find()
        if Doc == []:
            return None
        else:
            return {items["item"]: items["amount"] for items in Doc}
            
    def show_inventory(self):
        """打印當前庫存內容"""
        print("倉庫現況：")
        Doc = self.get_inventory()
        
        if Doc != None:
            for item, amount in Doc.items():
                print(f"    {item}: {amount} 件")
        else:
            print(f"    倉庫為空")
      
    def send_keep(self):
        """寄送打包"""
        if self.keep_list != []:
            print(f'執行中，共 {len(self.keep_list)} 筆:')
            for i in self.keep_list:
                self.__write_to_db(*i)
            
            self.keep_list = []
        else:
            print(f'目前無打包')

    def __write_to_db(self, type, item, amount, time):
        # 重新獲取日期
        self.collection = self.__today_collection
        
        # 取得現有庫存
        item_doc = self.inventory.find_one({"item": item})
        current_amount = item_doc["amount"] if item_doc else 0

        if type == "in":
            new_amount = current_amount + amount
        elif type == "out":
            if current_amount < amount:
                print(f"警告: 紀錄目標 {item} 為負數，當前: {current_amount}，目標: {current_amount - amount}，已忽略此筆。")
                return None
            else:
                new_amount = current_amount - amount

        # 更新或新增庫存
        self.inventory.update_one(
            {"item": item},
            {"$set": {"amount": new_amount}},
            upsert=True
        )

        # 寫入當天的紀錄表
        record = {
            "type": type,
            "item": item,
            "amount": amount,
            "time": time
        }
        result = self.collection.insert_one(record)
        print(f"紀錄 [{type}] {item}*{amount} 成功，紀錄 ID: {result.inserted_id}")
        
        # 刪除歸零倉庫位
        if (new_amount == 0):
            self.inventory.delete_one({"amount":0})
    
    @property
    def __today_collection(self):
        """當日資料表"""
        return self.db[f"{datetime.date.today()}"]
        
        
if __name__ == '__main__':
    depot = Depot()