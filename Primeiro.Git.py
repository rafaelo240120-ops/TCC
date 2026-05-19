import pandas as pd
import requests



# A base de dados foi retirada do site da B3, onde tem os dados históricos do ISE B3 e do IBrX-100.
# Na primeira versão do TCC, a base de dados foi retirada via API, onde tem os dados históricos do ISE B3 e do IBrX-100, mas o código ficou muito grande,
# então baixei os dados dos dois semestres dispomibilizados no site da B3 dos anos de 2015 a 2025, manualmente, e juntei os dados dos dois ativos em um único arquivo Excel, 
# onde tem os dados diarios do ISE B3 e do IBrX-100.

base = pd.read_excel(r"C:\Users\rafin\OneDrive\Documentos\TCC GITHUB\base_ise_ibrx.xlsx")

base.head(20)
base.tail(20)
base.info()
base.shape
base.columns
base.dtypes
base.isna().sum()
base 

# Garantindo que as colunas estao no tipo certo

base["data"] = pd.to_datetime(base["data"])
base["ise_b3"] = base["ise_b3"].astype(float)
base["ibrx100"] = base["ibrx100"].astype(float)

base.info()


# Agora vamos pegar a Selic diaria pela API do Banco Central.
# Vamos usar essa taxa como taxa livre de risco.

codigo = 11
url = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"

params1 = {
    "formato": "json",
    "dataInicial": "01/01/2015",
    "dataFinal": "31/12/2024"
}

params2 = {
    "formato": "json",
    "dataInicial": "01/01/2025",
    "dataFinal": "31/12/2025"
}

response1 = requests.get(url, params=params1)
response1.status_code
dados1 = response1.json()

response2 = requests.get(url, params=params2)
response2.status_code
dados2 = response2.json()

dados = dados1 + dados2
selic = pd.DataFrame(dados)

selic.head()
selic.info()

selic["data"] = pd.to_datetime(selic["data"], dayfirst=True)
selic["valor"] = selic["valor"].astype(float)

selic = selic.rename(columns={"valor": "selic_dia"})

selic.head()
selic.info()


# Juntar ISE, IBrX e Selic pela coluna data.

base = pd.merge(base, selic, on="data", how="left")

base.head()
base.tail()
base.info()
