# Origem e preparação dos dados

Toda a simulação, inferência, conferências, tabelas e figuras estão no único .py. Os dados de entrada foram preparados e congelados separadamente. A opção adotada é documentar as fontes por arquivo, sem adicionar um segundo programa de preparação à entrega.

- [precos.csv](origem/precos.csv.md)
- universo_amplo.csv e as listas do ISE no código ([origem](origem/universos.csv.md))
- códigos renomeados, no código ([origem](origem/aliases.json.md))
- [eventos.json](origem/eventos.json.md)
- [base_ise_ibrx_selic.csv](origem/base_ise_ibrx_selic.csv.md)
- [nefin_fatores.csv](origem/nefin_fatores.csv.md)
- [pendencias.json](origem/pendencias.json.md)
- [Fundamentos: fonte, data e hash por snapshot](origem/fundamentos.md)
- universos_anteriores.csv: listas do ISE B3 da versão anterior do estudo, usadas só na sensibilidade às listas (TCC 4.6)
- [Listas do ISE e ponderação dos índices](LISTAS_ISE_E_PONDERACAO.md) e [catálogo dos eventos societários](CATALOGO_EVENTOS.md)

Os documentos oficiais estão em fontes/. Os metadados de consulta estão ao lado das respostas no cache e em fontes/fontes_consultadas.json e fontes/fontes_eventos.json. As versões anteriores dos dados (controle_original/), usadas apenas para reconstituir o código anterior às correções, ficaram no pacote do código auditado (TCC_arquivo_unico/dados/controle_original). Datas antigas desconhecidas são declaradas como desconhecidas, sem usar o horário de cópia como se fosse coleta. Cada execução também grava os hashes efetivamente utilizados em resultados/execucao.json.
