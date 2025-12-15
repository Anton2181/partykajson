from PyQt6.QtWidgets import QTreeWidgetItem

class NumericSortItem(QTreeWidgetItem):
    def __lt__(self, other):
        column = self.treeWidget().sortColumn()
        key1 = self.text(column)
        key2 = other.text(column)
        
        # Attempt numeric conversion for sorting
        try:
            return float(key1) < float(key2)
        except ValueError:
            return key1 < key2
