from flask import Flask, render_template, request, redirect, url_for, jsonify
from depot import Depot, DepotItem, DepotError


# ==== 初始化設定 ====
app = Flask(__name__)
depot = Depot()


@app.route("/")
def index():
    inventory = depot.get_inventory()
    items = list(inventory.keys()) if inventory else None
    return render_template("index.html", items=items)


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

        depot.write(small, "web")
        depot.write(big, "web")
        depot.write(tube, "web")
        print(f"[Depot]-info: write_down")
    except DepotError as err:
        print(f"[Depot]-error: {err}")
        return jsonify({"status": "error", "message": f"deta_bad: {err}"})

    return jsonify({"status": "success", "message": "deta_ok"})


if __name__ == "__main__":
    app.run(debug=True)
