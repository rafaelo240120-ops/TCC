# Código do TCC: factor investing no universo do ISE B3 (2016 a 2025)

Rafael Diniz Oliveira, Ciências Econômicas, Faculdade Ibmec de Brasília.
Orientador: Prof. Laerte Jun Takeuti.

Todo o estudo está em um único arquivo, `carteira_factor_investing.py`. O cabeçalho do arquivo
explica o que ele faz e mostra em que parte do código está cada seção, tabela e gráfico do TCC.

## Como rodar

1. Instale o Python 3.11 ou mais recente.
2. Nesta pasta, instale as bibliotecas nas versões usadas no TCC:

   ```
   python -m pip install -r requirements.txt
   ```

3. Ainda nesta pasta, rode o estudo (cerca de 10 segundos):

   ```
   python carteira_factor_investing.py
   ```

O estudo roda sem internet e sem token, porque todos os dados usados estão na pasta `dados/`.
A tela mostra as Tabelas 1 a 9 do TCC e os números citados no texto, e tudo é gravado em
`resultados/`. Com as versões de `requirements.txt`, os resultados saem iguais aos do TCC.

## Onde colocar o token do Laboratório de Finanças

O token não é necessário para rodar o estudo. As consultas de P/VP, ROIC e setor feitas na API
do Laboratório de Finanças estão guardadas em `dados/fundamentos`, uma para cada data de sinal,
com a data da consulta e um código de verificação (SHA-256).

Para baixar essas consultas de novo da API:

1. Abra `carteira_factor_investing.py` e vá à Parte 1 (Configuração):

   ```python
   TOKEN_LAB_FINANCAS = ""
   ```

2. Cole o token entre as aspas.
3. Na linha seguinte, troque `False` por `True`:

   ```python
   ATUALIZAR_FUNDAMENTOS = True
   ```

4. Rode o estudo normalmente.

As consultas baixadas substituem as guardadas. Se a API devolver hoje os mesmos dados de quando o
estudo foi feito, os resultados são os mesmos. Para não perder as consultas originais, faça isso
numa cópia desta pasta. Não divulgue o código com o token preenchido.

## Onde está cada resultado do TCC

| No TCC | Arquivo em `resultados/` |
|---|---|
| Tabela 1 – Número de ações em cada ano | `tabela_1_acoes_por_ano.csv` |
| Tabela 2 – Desempenho das carteiras e dos índices | `tabela_2_desempenho.csv` |
| Tabela 3 – Retorno de cada ano | `tabela_3_retorno_de_cada_ano.csv` |
| Tabela 4 – Quedas do IBrX-100 e recuperações | `tabela_4_quedas_e_recuperacoes.csv` |
| Tabela 5 – Setores | `tabela_5_setores.csv` |
| Tabela 6 – Custos de negociação | `tabela_6_custos.csv` |
| Tabela 7 – Vantagem da Multifator em dois passos | `tabela_7_vantagem_em_dois_passos.csv` |
| Tabela 8 – Maior queda acumulada em dois passos | `tabela_8_queda_em_dois_passos.csv` |
| Tabela 9 – Ciclo completo de cada queda | `tabela_9_ciclos_completos.csv` |
| Apêndice A – Ações de cada carteira, ano a ano | `apendice_A_acoes_de_cada_carteira.csv` |
| Números citados no texto, com a seção | `numeros_citados_no_texto.csv` |
| Gráficos 1 a 3 | `figuras/` |

As tabelas estão no formato do Excel em português (ponto e vírgula entre colunas e vírgula
decimal). A pasta `resultados/detalhes/` traz os dados completos, sem arredondamento: retornos
diários, fatores de cada ação, composições, exclusões, remontagens e custos, eventos, quedas e
setores.

## Os dados

As ações do ISE B3 de cada ano e os códigos que mudaram estão escritos no próprio código (Parte 2).
Os demais dados estão em `dados/`:

- `precos.csv`: fechamentos diários ajustados por proventos e desdobramentos das ações usadas no
  estudo, da API "preço corrigido" do Laboratório de Finanças, com o Yahoo Finance como fonte
  alternativa.
- `indices_e_selic.csv`: valores diários do ISE B3 e do IBrX-100, das estatísticas históricas
  publicadas pela B3, e a taxa Selic anual, série 1178 do Banco Central do Brasil.
- `fundamentos/`: as dez consultas de P/VP, ROIC e setor à API do Laboratório de Finanças, uma por
  data de sinal. O código confere o SHA-256 de cada consulta e recusa qualquer dado com data
  posterior ao sinal.
- `eventos.json` e `documentos_eventos/`: os eventos societários aplicados às carteiras (compra da
  SulAmérica pela Rede D'Or, da AES Brasil pela Auren, da BRF pela Marfrig e as duas etapas da
  conversão das ações da Copel), com a relação de troca e o documento de cada um.

Não altere os arquivos de `dados/`: o código confere a origem das consultas e os resultados do TCC
dependem desses arquivos.
