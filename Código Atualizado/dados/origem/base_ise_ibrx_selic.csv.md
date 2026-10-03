# Origem: base_ise_ibrx_selic.csv

Fonte: níveis diários de fechamento do ISE B3 e do IBrX-100, das estatísticas históricas publicadas pela B3, e taxa Selic anualizada (base 252), série 1178 do Sistema Gerenciador de Séries Temporais do Banco Central do Brasil. Base reunida pelo autor.

Conferência com as fontes oficiais (02/10/2026): os 2.729 fechamentos do ISE B3, os 2.729 do IBrX-100 e as 2.729 taxas Selic da base são idênticos aos valores publicados pela B3 e pelo Banco Central. As séries oficiais consultadas estão em fontes/indices_b3_estatisticas_historicas.csv e fontes/selic_bcb_sgs1178.csv, com os endereços em fontes/fontes_oficiais_indices_selic.json. O programa repete essa conferência a cada execução e interrompe o cálculo se houver qualquer diferença.

Procedimento: retornos calculados a partir dos níveis e início alinhado no fechamento da primeira compra. Selic diária = (1 + taxa anual/100)^(1/252) - 1.

SHA-256 da base: `0ac4e5d4e3ba37347c205a68812ddb8c76ffba63ae294129cdf1407a34f73d82`
