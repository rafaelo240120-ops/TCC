# Origem: universos.csv

> **Nesta versão do código:** as listas do ISE B3 estão escritas no próprio código (`LISTAS_ISE`, Parte 2), com a mesma ordem e as mesmas datas; o universo amplo está em `entrada/universo_amplo.csv`. O arquivo `universos.csv` descrito abaixo, que reunia os dois, continua no pacote do código auditado (`TCC_arquivo_unico/dados/entrada`).

Fonte: ISE: portal histórico ISE B3 e BDIs oficiais. Amplo: cache recebido do endpoint /api/v2/preco/estatistica, campo volume1y.

Data de obtenção: Listas herdadas sem data de consulta original. BDIs e portal baixados em 10/09/2026; revisão das listas e CYRE3 em 12/09/2026.

Procedimento e correções: ISE: listas e classes recebidas, com correções temporais. Regra: última seleção definitiva anunciada até o fechamento-sinal, atualizada por exclusões já conhecidas. Detalhes em LISTAS_ISE_E_PONDERACAO.md. Amplo: para cada sinal, busca retrocede até 30 dias de calendário até obter resposta; ordena volume1y positivo decrescente e escolhe 100 ativos. O procedimento foi lido no código original; a resposta completa da API não foi preservada nesta base.

Limitação: O amplo é uma aproximação por volume, não a carteira histórica oficial do IBrX-100. Em 2023 são 70 ativos; 2024 são 66; 2025 são 76 após inclusão de CYRE3. Disponivel_em é controle temporal, não prova de vintage do fornecedor. 2016–2022 mantêm pendências por classe; anúncio não significa vigência.

SHA-256 da versão documentada: `6fc87a76001c56fc4c4e6201809a21f18afbe2f0548f2a56dd6f8d34eae84217`

Registro documental: 2026-09-13T13:29:36.926020+00:00. O hash identifica a versão, não demonstra exatidão econômica.
