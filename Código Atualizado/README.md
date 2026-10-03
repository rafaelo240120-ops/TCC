# Código do TCC: factor investing no universo do ISE B3 (2016 a 2025)

Autor: Rafael Diniz Oliveira

Todo o estudo está em um único arquivo: `carteira_factor_investing.py`.
O cabeçalho do arquivo mostra a ordem do estudo e a seção do TCC de cada parte.
As ações do ISE B3 de cada ano estão escritas no próprio código (Parte 2), e a
execução mostra na tela as carteiras escolhidas em cada ano.

## Como rodar

1. Instale o Python 3.11 ou mais recente.
2. Nesta pasta, instale as bibliotecas nas versões usadas no TCC:

   ```
   python -m pip install -r requirements.txt
   ```

3. Ainda nesta pasta, rode o estudo completo (cerca de 2 minutos):

   ```
   python carteira_factor_investing.py
   ```

   ou só os testes internos (alguns segundos):

   ```
   python carteira_factor_investing.py --testar
   ```

O estudo roda sem internet e sem token: todos os dados usados estão na pasta `dados/`.
Ao final, a tela mostra o desempenho (Tabela 3 do TCC) e os testes de Sharpe (Tabela 6).

## Onde colocar o token do Laboratório de Finanças

O token não é necessário para rodar o estudo. As consultas de P/VP e ROIC feitas na API
do Laboratório de Finanças estão guardadas em `dados/cache`, cada uma com a data da consulta
e um código de verificação.

Para baixar essas consultas de novo da API:

1. Abra `carteira_factor_investing.py` e vá à Parte 1 (Configuração), linha 107:

   ```python
   TOKEN_LAB_FINANCAS = ""
   ```

2. Cole o token entre as aspas.
3. Na linha seguinte, troque `False` por `True`:

   ```python
   ATUALIZAR_FUNDAMENTOS = True
   ```

4. Rode o estudo normalmente.

As consultas baixadas substituem as guardadas em `dados/cache`. Se a API devolver hoje os mesmos
dados de quando o estudo foi feito, os resultados são os mesmos. Para não perder as consultas
originais, faça isso numa cópia desta pasta. Não publique o código com o token preenchido.

## Pastas

- `dados/`: entradas do estudo e a documentação de cada uma (não altere).
- `resultados/`: tabelas (.csv), gráficos (`figuras/`) e o registro da execução (`execucao.json`).
  A pasta já traz os resultados do TCC, e cada execução grava tudo de novo. Ao lado de cada
  arquivo gravado, o código indica a tabela do TCC que sai dele.

Para comparar a sua execução com os resultados do TCC, copie a pasta `resultados/` antes de
rodar e compare os arquivos depois. Com as versões de `requirements.txt`, as tabelas saem
iguais às do TCC.
