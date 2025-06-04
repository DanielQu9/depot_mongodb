import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from depot import Depot


class WarehouseGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("倉儲管理系統")
        self.root.geometry("700x400")
        self.depot = Depot()
        
        # === 主視窗：顯示倉庫剩餘量的區塊 ===
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Label 標題
        lbl = ttk.Label(main_frame, text="倉庫剩餘量", font=("Arial", 14))
        lbl.pack(anchor=tk.W)
        
        # 用 Text widget 放倉庫剩餘量 (可換成 Treeview 或 Listbox)
        self.inventory_text = tk.Text(main_frame, height=10, wrap=tk.NONE, font=("Arial", 12))
        self.inventory_text.pack(fill=tk.BOTH, expand=True, pady=(5, 10))
        
        self.update_main_inventory()
        
        # 開啟副視窗按鈕
        btn_open = ttk.Button(main_frame, text="操作", command=self.open_secondary_window)
        btn_open.pack(anchor=tk.CENTER)
    
    def open_secondary_window(self):
        """建立並顯示副視窗 (Toplevel)"""
        # 若副視窗已存在，則把它提到最上層
        if hasattr(self, 'sec_win') and self.sec_win.winfo_exists():
            self.sec_win.lift()
            return
        
        self.sec_win = tk.Toplevel(self.root)
        self.sec_win.title("出/入庫操作")
        self.sec_win.geometry("600x400")
        
        # 左右兩側容器
        left_frame = ttk.Frame(self.sec_win, padding=10)
        right_frame = ttk.Frame(self.sec_win, padding=10)
        left_frame.pack(side=tk.LEFT, fill=tk.Y)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # === 左側區域 ===
        # 1. 單選按鈕：入庫 / 出庫
        self.io_var = tk.StringVar(value="in")
        lbl_io = ttk.Label(left_frame, text="操作模式：")
        lbl_io.grid(row=0, column=0, sticky=tk.W, pady=(0,5))
        rb_in = ttk.Radiobutton(left_frame, text="入庫", variable=self.io_var, value="in")
        rb_out = ttk.Radiobutton(left_frame, text="出庫", variable=self.io_var, value="out")
        rb_in.grid(row=1, column=0, sticky=tk.W)
        rb_out.grid(row=1, column=1, sticky=tk.W)
        
        # 2. 物品名稱 & 數量 輸入框
        lbl_name = ttk.Label(left_frame, text="物品名稱：")
        lbl_qty  = ttk.Label(left_frame, text="數量：")
        self.entry_name = ttk.Entry(left_frame)
        self.entry_qty  = ttk.Entry(left_frame)
        lbl_name.grid(row=2, column=0, sticky=tk.W, pady=(10,2))
        self.entry_name.grid(row=3, column=0, columnspan=2, sticky=tk.EW)
        lbl_qty.grid(row=4, column=0, sticky=tk.W, pady=(10,2))
        self.entry_qty.grid(row=5, column=0, columnspan=2, sticky=tk.EW)
        
        # 3. 送出 & 重置 按鈕
        btn_submit = ttk.Button(left_frame, text="送出", command=self.add_to_list)
        btn_reset  = ttk.Button(left_frame, text="重置", command=self.reset_inputs)
        btn_submit.grid(row=6, column=0, pady=(20,0), sticky=tk.EW)
        btn_reset.grid(row=6, column=1, pady=(20,0), sticky=tk.EW)
        
        # 讓左側欄位寬度可以伸縮
        left_frame.columnconfigure(0, weight=1)
        left_frame.columnconfigure(1, weight=1)
        
        # === 右側區域 ===
        # 上方：全選按鈕
        btn_select_all = ttk.Button(right_frame, text="全選", command=self.select_all_items)
        btn_select_all.pack(anchor=tk.W)
        
        # 中間：顯示動態清單 (滾動視窗 + Frame)
        list_container = ttk.Frame(right_frame)
        list_container.pack(fill=tk.BOTH, expand=True, pady=(5,5))
        
        # 建立 Canvas + Scrollbar
        self.canvas = tk.Canvas(list_container)
        vsb = ttk.Scrollbar(list_container, orient="vertical", command=self.canvas.yview)
        self.inner_frame = ttk.Frame(self.canvas)
        
        self.inner_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            )
        )
        self.canvas.create_window((0, 0), window=self.inner_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=vsb.set)
        
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 用來儲存每一筆清單的勾選狀態與參考
        self.item_vars = []   # List of (tk.BooleanVar, frame, label_text)
        
        # 下方：「送出已勾選」與「移除已勾選」
        btn_submit_checked = ttk.Button(right_frame, text="送出已勾選", command=self.submit_checked_items)
        btn_remove_checked = ttk.Button(right_frame, text="移除已勾選", command=self.remove_checked_items)
        btn_submit_checked.pack(anchor=tk.E, pady=(5, 2))
        btn_remove_checked.pack(anchor=tk.E, pady=(0, 5))
    
    def reset_inputs(self):
        """清空左側所有輸入欄位及單選按鈕"""
        self.io_var.set("in")
        self.entry_name.delete(0, tk.END)
        self.entry_qty.delete(0, tk.END)
    
    def add_to_list(self):
        """把左側輸入的項目加到右側的清單 (含勾選框)"""
        mode = self.io_var.get()               # "in" 或 "out"
        name = self.entry_name.get().strip()
        qty_text = self.entry_qty.get().strip()
        if not name or not qty_text.isdigit():
            messagebox.showwarning("輸入錯誤", "請正確填寫「物品名稱」及整數「數量」。")
            return
        
        qty = int(qty_text)
        display_text = f"[{'入' if mode=='in' else '出'}]  {name}  x {qty}"
        
        # 在右側新增一列：Checkbutton + Label
        var = tk.BooleanVar(value=False)
        row_frame = ttk.Frame(self.inner_frame)
        chk = ttk.Checkbutton(row_frame, variable=var)
        lbl = ttk.Label(row_frame, text=display_text)
        chk.pack(side=tk.LEFT)
        lbl.pack(side=tk.LEFT, padx=(5,0))
        row_frame.pack(anchor=tk.W, fill=tk.X, pady=2)
        
        # 紀錄下來，以便全選 / 批次處理
        self.item_vars.append((var, row_frame, display_text))
        
        # 重置左側欄位
        self.reset_inputs()
    
    def select_all_items(self):
        """把目前所有右側清單的勾選框都設為 True"""
        for var, frame, txt in self.item_vars:
            var.set(True)
    
    def submit_checked_items(self):
        """
        把右側所有已勾選項目，透過倉庫函式庫更新到資料庫，
        並且從清單上移除，最後同時更新主畫面上的「倉庫剩餘量」列表。
        """
        # 收集所有已勾選的 (BooleanVar, frame, display_text) tuple
        to_send = [ (var, frame, txt) for var, frame, txt in self.item_vars if var.get() ]
        if not to_send:
            messagebox.showinfo("無項目", "請先勾選要送出的項目。")
            return
        
        # 逐筆處理
        for var, frame, txt in to_send:
            # 解析 display_text 以取得模式、品名、數量
            # 範例格式："[入]  Apples  x 10" 或 "[出]  Bananas  x 5"
            parts = txt.split()
            mode_char = parts[0].strip("[]")   # "入" 或 "出"
            name = parts[1]
            qty = int(parts[3])
            
            # 根據入/出庫呼叫您的套件
            if mode_char == "入":
                self.depot.write(type='in', item=name, amount=qty, keep=True)
            else:
                self.depot.write(type='out', item=name, amount=qty, keep=True)
            
            # 從介面上移除該列
            frame.destroy()
            self.item_vars.remove((var, frame, txt))
            self.depot.send_keep()
        
        # 執行完畢後，更新主視窗的庫存列表
        self.update_main_inventory()
        messagebox.showinfo("完成", "已將勾選項目送出且更新主畫面。")

    def remove_checked_items(self):
        """
        只從右側清單中移除所有已勾選項目，不呼叫任何庫存更新
        """
        to_remove = [ (var, frame, txt) for var, frame, txt in self.item_vars if var.get() ]
        if not to_remove:
            messagebox.showinfo("無項目", "請先勾選要移除的項目。")
            return
        
        for var, frame, txt in to_remove:
            frame.destroy()
            self.item_vars.remove((var, frame, txt))
        
        messagebox.showinfo("完成", "已從清單中移除勾選項目。")
        
    def update_main_inventory(self):
        """
        重新從倉庫函式庫抓取最新剩餘量，並覆寫到主視窗的 Text 物件。
        """
        # 清空舊內容
        self.inventory_text.delete("1.0", tk.END)
        
        # 輸出當前倉庫內容
        inventory = self.depot.get_inventory()
        # 假設 inventory 回傳 dict: { "Apples": 50, "Bananas": 20, ... }
        if inventory != None:
            for item in inventory:
                self.inventory_text.insert(tk.END, f"{item["item"]}: {item["amount"]}\n")

if __name__ == "__main__":
    root = tk.Tk()
    app = WarehouseGUI(root)
    root.mainloop()
