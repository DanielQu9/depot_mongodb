from flask import Flask, render_template, request, redirect, url_for, jsonify
from depot import Depot


# ==== 初始化設定 ====
app = Flask(__name__)
depot = Depot()


@app.route('/')
def index():
    inventory = depot.get_inventory()
    items = list(inventory.keys()) if inventory != None else None
    return render_template('index.html', items=items)

@app.route('/api/data')
def api_data():
    """回傳: item, count, unit_weight, min_weight_warning"""
    item = request.args.get('item')
    if not item:
        return jsonify({})
    inventory = depot.get_inventory()
    # 明確指定要查 tag 的 item
    tag = depot.get_tag_json(item)
    count = inventory.get(item, 0) if inventory != None else 0
    unit_w = tag.get('unit_weight', 0) if tag != None else 0
    min_w = tag.get('min_weight_warning', 0) if tag != None else 0
    return jsonify({
        'item': item,
        'count': count,
        'unit_weight': unit_w,
        'min_weight': min_w
    })

if __name__ == '__main__':
    app.run(debug=True)