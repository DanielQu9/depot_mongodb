from depot import Depot


db = Depot()

db.show_inventory()
db.write('out', "螺公", 1)
db.show_inventory()