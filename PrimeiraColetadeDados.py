import pandas as pd

# A base de dados foi retirada do site da B3.
# Baixei os dados historicos do ISE B3 e do IBrX-100 dos anos de 2015 a 2025.
# Depois, juntei os dados dos dois indices em uma unica planilha.
# A Selic tambem foi colocada na mesma planilha, para ser usada como taxa livre de risco.

base = pd.read_excel(r"C:\Users\rafin\OneDrive\Documentos\TCC GITHUB\base_ise_ibrx.xlsx")

base.head(20)
base.tail(20)
base.info()
base.shape
base.columns
base.dtypes
base.isna().sum()

# Garantindo que as colunas estao no tipo certo

base["data"] = pd.to_datetime(base["data"])
base["ise_b3"] = base["ise_b3"].astype(float)
base["ibrx100"] = base["ibrx100"].astype(float)
base["selic_aa"] = base["selic_aa"].astype(float)

base.info()
base.head()
