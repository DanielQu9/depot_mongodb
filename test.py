from depot import Depot


db = Depot()

db.show_inventory()
db.write('in', "64test1", 1)
db.show_inventory()