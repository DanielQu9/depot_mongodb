import json
import tkinter as tk
from tkinter import ttk, messagebox
from depot import Depot, DepotItem, DepotError


class WarehouseGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("倉儲管理系統")
        self.root.geometry("700x400")
        self.depot = Depot()

        # === 主視窗：顯示倉庫剩餘量的區塊 ===
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # title 區塊
        title_frame = ttk.Frame(main_frame)
        title_frame.pack(fill=tk.X)

        # Label 標題
        lbl = ttk.Label(title_frame, text="倉庫剩餘量", font=("Arial", 14))
        lbl.pack(side=tk.LEFT)

        # 用 Text widget 放倉庫剩餘量 (可換成 Treeview 或 Listbox)
        self.inventory_text = tk.Text(
            main_frame, height=10, wrap=tk.NONE, font=("Arial", 12)
        )
        self.inventory_text.pack(fill=tk.BOTH, expand=True, pady=(5, 10))

        self.update_main_inventory()

        # 開啟副視窗按鈕
        btn_open = ttk.Button(
            main_frame, text="操作", command=self.open_secondary_window
        )
        btn_open.pack(anchor=tk.CENTER)

        # 開啟TAG設定按鈕
        tag_open = ttk.Button(
            main_frame, text="TAG設定", command=self.open_tag_setting_window
        )
        tag_open.pack(anchor=tk.NE)

        # 重新整理按鈕
        btn_refresh = ttk.Button(
            title_frame, text="🔄", command=self.update_main_inventory
        )
        btn_refresh.pack(side=tk.RIGHT)

    def open_secondary_window(self):
        """建立並顯示副視窗 (Toplevel)"""
        # 若副視窗已存在，則把它提到最上層
        if hasattr(self, "sec_win") and self.sec_win.winfo_exists():
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
        lbl_io.grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        rb_in = ttk.Radiobutton(
            left_frame, text="入庫", variable=self.io_var, value="in"
        )
        rb_out = ttk.Radiobutton(
            left_frame, text="出庫", variable=self.io_var, value="out"
        )
        rb_in.grid(row=1, column=0, sticky=tk.W)
        rb_out.grid(row=1, column=1, sticky=tk.W)

        # 2. 物品名稱 & 數量 輸入框
        lbl_name = ttk.Label(left_frame, text="物品名稱：")
        lbl_qty = ttk.Label(left_frame, text="數量：")
        # self.entry_name = ttk.Entry(left_frame)  # 名稱輸入
        self.item_name_var = tk.StringVar()  # 選單變數
        self.combo_name = ttk.Combobox(
            left_frame, textvariable=self.item_name_var, state="normal"
        )  # 名稱輸入但有選單
        self.entry_qty = ttk.Entry(left_frame)
        lbl_name.grid(row=2, column=0, sticky=tk.W, pady=(10, 2))
        # self.entry_name.grid(row=3, column=0, columnspan=2, sticky=tk.EW)
        self.combo_name.grid(row=3, column=0, columnspan=2, sticky=tk.EW)
        lbl_qty.grid(row=4, column=0, sticky=tk.W, pady=(10, 2))
        self.entry_qty.grid(row=5, column=0, columnspan=2, sticky=tk.EW)

        # 2-5. 輸入下拉選單
        self.update_item_combobox_options()

        # 3. 送出 & 重置 按鈕
        btn_submit = ttk.Button(left_frame, text="送出", command=self.add_to_list)
        btn_reset = ttk.Button(left_frame, text="重置", command=self.reset_inputs)
        btn_submit.grid(row=6, column=0, pady=(20, 0), sticky=tk.EW)
        btn_reset.grid(row=6, column=1, pady=(20, 0), sticky=tk.EW)

        # 讓左側欄位寬度可以伸縮
        left_frame.columnconfigure(0, weight=1)
        left_frame.columnconfigure(1, weight=1)

        # === 右側區域 ===
        # 上方：全選按鈕
        btn_select_all = ttk.Button(
            right_frame, text="全選", command=self.select_all_items
        )
        btn_select_all.pack(anchor=tk.W)

        # 中間：顯示動態清單 (滾動視窗 + Frame)
        list_container = ttk.Frame(right_frame)
        list_container.pack(fill=tk.BOTH, expand=True, pady=(5, 5))

        # 建立 Canvas + Scrollbar
        self.canvas = tk.Canvas(list_container)
        vsb = ttk.Scrollbar(
            list_container, orient="vertical", command=self.canvas.yview
        )
        self.inner_frame = ttk.Frame(self.canvas)

        self.inner_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.canvas.create_window((0, 0), window=self.inner_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=vsb.set)

        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        # 用來儲存每一筆清單的勾選狀態與參考
        self.item_vars = []  # List of (tk.BooleanVar, frame, label_text)

        # 下方：「送出已勾選」與「移除已勾選」
        btn_submit_checked = ttk.Button(
            right_frame, text="送出已勾選", command=self.submit_checked_items
        )
        btn_remove_checked = ttk.Button(
            right_frame, text="移除已勾選", command=self.remove_checked_items
        )
        btn_submit_checked.pack(anchor=tk.E, pady=(5, 2))
        btn_remove_checked.pack(anchor=tk.E, pady=(0, 5))

    def open_tag_setting_window(self):
        """
        開啟一個新視窗，編輯所選那一筆的 tag JSON。
        """
        win = tk.Toplevel(self.root)
        win.title("編輯物品 Tag")
        win.geometry("500x400")

        # ====== 上：選擇品項 ======
        ttk.Label(win, text="選擇物品：").pack(anchor=tk.W, padx=10, pady=(10, 2))

        selected_name = tk.StringVar()
        self.tag_combo = ttk.Combobox(win, textvariable=selected_name, state="readonly")
        self.tag_combo.pack(fill=tk.X, padx=10)

        # 從倉庫讀取可選品項
        try:
            self.update_item_combobox_options()
        except Exception as e:
            messagebox.showerror("錯誤", f"無法讀取品項清單：{e}")
            return

        # ====== 顯示 tag JSON 的 Text ======
        ttk.Label(win, text="Tag JSON(請務必知道自己在修改什麼):").pack(
            anchor=tk.W, padx=10, pady=(10, 0)
        )
        txt = tk.Text(win, height=10)
        txt.pack(fill=tk.BOTH, expand=True, padx=10, pady=(2, 10))

        # 當選擇品項時 → 載入 tag
        def on_item_selected(event):
            name = selected_name.get()
            try:
                tag = self.depot.get_tag_json(name)
                # tag = doc.get("tag", {})
            except Exception as e:
                messagebox.showerror("錯誤", f"無法載入資料：{e}")
                return
            txt.delete("1.0", tk.END)
            txt.insert("1.0", json.dumps(tag, ensure_ascii=False, indent=2))

        self.tag_combo.bind("<<ComboboxSelected>>", on_item_selected)

        # ====== 儲存按鈕 ======
        def save_tag():
            name = selected_name.get()
            if not name:
                messagebox.showwarning("請選擇物品", "請先從清單中選擇一個物品")
                return
            raw = txt.get("1.0", tk.END).strip()
            try:
                tag_data = json.loads(raw)
            except json.JSONDecodeError as e:
                messagebox.showerror("格式錯誤", f"請輸入正確的 JSON：{e}")
                return
            try:
                self.depot.set_tag(name, tag_data)
                messagebox.showinfo("完成", f"{name} 的 tag 已更新")
                win.destroy()
                self.update_main_inventory()  # 若有需要同步主畫面
            except Exception as e:
                messagebox.showerror("更新失敗", f"無法更新 tag：{e}")

        ttk.Button(win, text="儲存", command=save_tag).pack(pady=(0, 10))

    def reset_inputs(self):
        """清空左側所有輸入欄位及單選按鈕"""
        self.io_var.set("in")
        self.item_name_var.set("")
        # self.entry_name.delete(0, tk.END)
        self.entry_qty.delete(0, tk.END)

    def add_to_list(self):
        """把左側輸入的項目加到右側的清單 (含勾選框)"""
        mode = self.io_var.get()  # "in" 或 "out"
        name = self.item_name_var.get().strip()
        qty_text = self.entry_qty.get().strip()
        if not name or not qty_text.isdigit():
            messagebox.showwarning("輸入錯誤", "請正確填寫「物品名稱」及整數「數量」。")
            return

        qty = int(qty_text)
        display_text = f"[{'入' if mode=='in' else '出'}]  {name}  x {qty}"

        # 建立DepotItem
        try:
            dp_item = DepotItem(mode, name, qty)  # type: ignore
        except DepotError as e:
            messagebox.showwarning("輸入錯誤", e.message)
            return

        # 在右側新增一列：Checkbutton + Label
        var = tk.BooleanVar(value=False)
        row_frame = ttk.Frame(self.inner_frame)
        chk = ttk.Checkbutton(row_frame, variable=var)
        lbl = ttk.Label(row_frame, text=display_text)
        chk.pack(side=tk.LEFT)
        lbl.pack(side=tk.LEFT, padx=(5, 0))
        row_frame.pack(anchor=tk.W, fill=tk.X, pady=2)

        # 紀錄下來，以便全選 / 批次處理
        self.item_vars.append((var, row_frame, display_text, dp_item))

        # 重置左側欄位
        self.reset_inputs()

    def select_all_items(self):
        """把目前所有右側清單的勾選框都設為 True"""
        for var, frame, txt, item in self.item_vars:
            var.set(True)

    def submit_checked_items(self):
        """
        把右側所有已勾選項目，透過倉庫函式庫更新到資料庫，
        並且從清單上移除，最後同時更新主畫面上的「倉庫剩餘量」列表。
        """
        # 收集所有已勾選的 (BooleanVar, frame, display_text) tuple
        to_send = [
            (var, frame, txt, item)
            for var, frame, txt, item in self.item_vars
            if var.get()
        ]
        if not to_send:
            messagebox.showinfo("無項目", "請先勾選要送出的項目。")
            return

        # 逐筆處理
        for var, frame, txt, item in to_send:
            # 解析 display_text 以取得模式、品名、數量
            # 範例格式："[入]  Apples  x 10" 或 "[出]  Bananas  x 5"
            parts = txt.split()
            mode_char = parts[0].strip("[]")  # "入" 或 "出"
            name = parts[1]
            qty = int(parts[3])

            # 根據入/出庫呼叫您的套件
            try:
                self.depot.write(item=item)
            except DepotError as e:
                messagebox.showwarning("輸入錯誤", e.message)

            # 從介面上移除該列
            frame.destroy()
            self.item_vars.remove((var, frame, txt, item))

        # 執行完畢後，更新主視窗的庫存列表
        self.update_main_inventory()
        messagebox.showinfo("完成", "已將勾選項目送出且更新主畫面。")

        # 更新下拉選單
        self.update_item_combobox_options()

    def remove_checked_items(self):
        """
        只從右側清單中移除所有已勾選項目，不呼叫任何庫存更新
        """
        to_remove = [
            (var, frame, txt, item)
            for var, frame, txt, item in self.item_vars
            if var.get()
        ]
        if not to_remove:
            messagebox.showinfo("無項目", "請先勾選要移除的項目。")
            return

        for var, frame, txt, item in to_remove:
            frame.destroy()
            self.item_vars.remove((var, frame, txt, item))

        messagebox.showinfo("完成", "已從清單中移除勾選項目。")

    def update_main_inventory(self):
        """
        重新從倉庫函式庫抓取最新剩餘量，並覆寫到主視窗的 Text 物件。
        """
        # 啟用編輯
        self.inventory_text.config(state="normal")

        # 清空舊內容
        self.inventory_text.delete("1.0", tk.END)

        # 輸出當前倉庫內容
        inventory = self.depot.get_inventory()
        if inventory != None:
            for item, amount in inventory.items():
                self.inventory_text.insert(tk.END, f"{item}: {amount}\n")

        # 鎖定編輯
        self.inventory_text.config(state="disabled")

    def update_item_combobox_options(self):
        """
        更新副視窗中的下拉選單選項
        """
        inventory = self.depot.get_inventory()
        if not inventory:
            return

        combo_temp = list(inventory.keys())

        # 如果 secondary window 的 combo_name 存在且視窗尚在
        if hasattr(self, "combo_name") and self.combo_name.winfo_exists():
            self.combo_name["values"] = combo_temp

        # 如果 tag setting window 的 tag_combo 存在且視窗尚在
        if hasattr(self, "tag_combo") and self.tag_combo.winfo_exists():
            self.tag_combo["values"] = combo_temp


if __name__ == "__main__":
    root = tk.Tk()
    app = WarehouseGUI(root)
    root.mainloop()
