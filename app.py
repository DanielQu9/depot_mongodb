from flask import Flask, render_template, request, redirect, url_for, jsonify
from depot import Depot, DepotItem, DepotError, DepotMongo


# ==== 初始化設定 ====
app = Flask(__name__)
depot = Depot()
mg = DepotMongo()


@app.route("/")
def index():
    # side_items：可動態新增選單
    side_items = [
        {"name": "首頁", "endpoint": "home"},
        {"name": "倉庫", "endpoint": "inventory"},
        {"name": "出/入貨物", "endpoint": "inventory"},
        {"name": "貨物紀錄", "endpoint": "records"},
        {"name": "狀態", "endpoint": "inventory"},
        # 日後再加頁面，就在這邊添加
    ]
    return render_template("base.html", side_items=side_items)


@app.route("/home")
def home():
    """首頁"""
    return render_template("home.html")


@app.route("/inventory")
def inventory():
    """倉庫庫存"""
    inv = depot.get_inventory()
    return render_template("inventory.html", items=inv)


@app.route("/records")
def records():
    """進出貨紀錄-輸出列表"""
    table_list = mg.date_collections  # 獲取所有資料表
    return render_template("records.html", tables=table_list)


@app.route("/records/data")
def records_data():
    """進出貨紀錄-輸出紀錄"""
    table_name = request.args.get("date")
    data = mg.find_records(str(table_name))
    return render_template("records_data.html", data=data, date=table_name)


@app.route("/api/data")
def api_data():
    """回傳: item, count, unit_weight, min_weight_warning"""
    item = request.args.get("item")
    if not item:
        return jsonify({})
    inventory = depot.get_inventory()
    # 明確指定要查 tag 的 item
    tag = depot.get_tag_json(item)
    count = inventory.get(item, 0) if inventory else 0
    unit_w = tag.get("unit_weight", 0) if tag else None
    min_w = tag.get("min_weight_warning", 0) if tag else None
    return jsonify(
        {"item": item, "count": count, "unit_weight": unit_w, "min_weight": min_w}
    )


@app.route("/api/esp_send", methods=["POST"])
def get_esp_data():
    data = request.get_json()
    final = data.get("final", False)
    if (not data) or (final):
        return jsonify({"status": "error", "message": "deta_error"}), 400

    # 處理資料
    try:
        small = DepotItem("out", "small", data["small"])
        big = DepotItem("out", "big", data["big"])
        tube = DepotItem("out", "tube", data["tube"])

        depot.write(small, "esp")
        depot.write(big, "esp")
        depot.write(tube, "esp")
        print(f"[Depot]-info: write_down")
    except DepotError as err:
        print(f"[Depot]-error: {err}")
        return jsonify({"status": "error", "message": f"deta_bad: {err}"})

    return jsonify({"status": "success", "message": "deta_ok"})


if __name__ == "__main__":
    app.run(debug=True)
