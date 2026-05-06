import pandas as pd

# Data from the pstxnet.dat file
net_data = [
    {"net_name": "D3P2_TXP[0]", "node_a": "J10 B08", "node_b": "CONN2 C23"},
    {"net_name": "D3P2_TXN[0]", "node_a": "J10 B07", "node_b": "CONN2 D23"},
    {"net_name": "D3P2_TXP[1]", "node_a": "J10 B06", "node_b": "CONN2 E23"},
    {"net_name": "D3P2_TXN[1]", "node_a": "J10 B05", "node_b": "CONN2 F23"},
    {"net_name": "D3P2_TXP[2]", "node_a": "J10 A06", "node_b": "CONN2 G23"},
    {"net_name": "D3P2_TXN[2]", "node_a": "J10 A05", "node_b": "CONN2 H23"},
]

# Create DataFrames for each tab
net_name_df = pd.DataFrame({"Net Name": [entry["net_name"] for entry in net_data]})
node_a_df = pd.DataFrame({"Node Name A": [entry["node_a"] for entry in net_data]})
node_b_df = pd.DataFrame({"Node Name B": [entry["node_b"] for entry in net_data]})

# Create an Excel writer
with pd.ExcelWriter("pstxnet_data.xlsx") as writer:
    net_name_df.to_excel(writer, sheet_name="Net Name", index=False)
    node_a_df.to_excel(writer, sheet_name="Node Name A", index=False)
    node_b_df.to_excel(writer, sheet_name="Node Name B", index=False)

print("Excel file 'pstxnet_data.xlsx' has been created.")