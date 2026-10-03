# Origem: precos.csv

Fonte: Laboratório de Finanças: /api/v2/preco/corrigido; Yahoo Finance como alternativa no código recebido; CPLE5 cruzada com COTAHIST B3. BRAV3: mesma API e escala nominal cruzada com COTAHIST 2024.

Data de obtenção: Cache herdado: data da coleta original e fornecedor por célula não preservados. Migração em 09/09/2026; CPLE5 obtida em 11/09/2026 (metadado no cache). BRAV3 obtida em 12/09/2026.

Procedimento e correções: Partiu de controle_original/precos_historicos_cache.csv. A revisão recuperou CPLE6 de data/precos_cache_ANTES_correcao.csv do acervo, sem substituir PNB por ON. Nesta etapa adicionou CPLE5 da resposta JSON preservada. Nenhum preenchimento artificial foi gravado nesta revisão; durante a simulação, posições sem cotação são valoradas pelo último preço e registradas. Acrescentada também BRAV3 desde 09/09/2024, com resposta e metadado preservados no cache.

Limitação: O código recebido substituía séries com menos observações ou menos de 90% de cobertura entre primeiro e último preço por uma nova série completa da API (alternativa Yahoo), somente quando aumentava a cobertura. O cache não preserva o histórico de todas essas substituições, nem ajustes corporativos por célula. A ausência dessa trilha não pode ser corrigida inventando datas. Quantidades são cotas sintéticas de preços ajustados, não ações físicas. Diferenças numéricas frente ao controle são resumidas em reparos_precos.csv.

SHA-256 da versão documentada: `d73ff4ddc39f6f4a4937b716df54b754c6d1b6515243882e09fbb51c84e510b2`

Registro documental: 2026-09-13T13:29:36.926020+00:00. O hash identifica a versão, não demonstra exatidão econômica.
