# Listas anuais do ISE e ponderação dos índices

## O que estava vigente e o que foi usado

Há duas datas diferentes: anúncio de uma lista e início da sua vigência. A regra desta simulação é usar a última seleção definitiva anunciada até o fechamento do sinal, considerando exclusões já conhecidas. Portanto, não se deve escrever que ela sempre usa a carteira que já estava vigente no sinal.

| Formação | Fechamento do sinal | Carteira então vigente | Seleção usada | Documentos |
|---|---|---|---|---|
| 2023 | 29/12/2022 | 17ª, anunciada em 29/12/2021, vigência de 03/01 a 30/12/2022 | 18ª, anunciada em 28/12/2022, vigência de 02/01 a 29/12/2023; 70 ativos | BDI 29/12/2022, prévia p. 65; BDI 02/01/2023, p. 24–25; portal histórico |
| 2024 | 28/12/2023 | 18ª, anunciada em 28/12/2022, vigência de 02/01 a 29/12/2023 | 18ª após exclusões conhecidas; 66 ativos | BDI 28/12/2023, p. 31–32; exclusões no portal histórico |
| 2025 | 30/12/2024 | 19ª, anunciada em 29/12/2023 e vigente desde 02/01/2024, com atualização em 06/05/2024 e exclusões posteriores | Lista atualizada da 19ª; 76 ativos | BDI 30/12/2024, p. 28–29; prévia p. 73; portal histórico; calendário B3 |

Os BDIs contêm tabelas de composição do período e prévias do período seguinte. Algumas tabelas ainda exibem nomes excluídos: em dezembro de 2023, BRKM5; em dezembro de 2024, AESB3. Foi necessário cruzar o boletim com as exclusões datadas, em vez de copiar uma tabela indiscriminadamente. A extração por ticker, página e tipo de tabela está em `dados/fontes/composicoes_ise_extraidas_bdi.csv`.

Em 2023, a lista anterior omitia BRKM5, ENBR3 e USIM5. A composição inicial de 70 foi confirmada no BDI do primeiro pregão de 2023. A exclusão posterior de um ativo não pode removê-lo retroativamente da lista inicial.

Em 2024, o anúncio definitivo da 19ª ocorreu em 29/12/2023, depois do sinal adotado, em 28/12. Existe uma prévia de 78 ativos no BDI de 28/12; isso corrige a afirmação anterior de que a prévia não estava disponível. Usar essa prévia seria outro desenho admissível, se declarado e aplicado consistentemente. A presente execução conserva a regra de anúncio definitivo: 18ª após AMER3 (23/01/2023), LIGT3 (16/05), ENBR3 (11/07) e BRKM5 (08/12). Essa escolha não significa que a 18ª permaneceu sendo o índice oficial durante 2024.

Em 2025, a 20ª carteira começou em **05/05/2025**, com o novo calendário anual de maio a abril. Ela não estava disponível para a formação no fechamento de 2024. A revisão anterior acertou ao afastar essa antecipação, mas omitiu **CYRE3**: o BDI de dezembro e a prévia de janeiro incluem esse ativo. A lista passa de 75 para 76. AESB3 é removida porque sua exclusão já havia ocorrido em 31/10/2024.

As listas anteriores ficam preservadas. `resultados/tabela1_duas_listas.csv` compara as duas sob as mesmas regras finais, inclusive eventos. As listas documentadas são mais defensáveis para a convenção de anúncio definitivo, mas não certificam automaticamente as classes de todos os anos nem o universo amplo. O contraste também depende da decisão sobre usar ou não as prévias; não existe uma única convenção possível.

## Ponderação: índice oficial e carteiras simuladas

Até a carteira de 2021, o ISE usava valor de mercado das ações em circulação (free float). A partir de **03/01/2022**, passou ao Score ISE B3, com teto de três vezes a participação que o ativo teria pelo free float e limite de 10% por empresa. A metodologia prevê revisões quadrimestrais, além do processo anual de seleção. A alteração do calendário anual em 2025 não transforma o histórico inteiro em uma mesma regra de ponderação.

O IBrX-100 é ponderado pelo valor de mercado do free float, segundo sua metodologia. As carteiras fatoriais desta simulação recebem pesos iguais na formação anual; os pesos flutuam depois. Elas não reproduzem os pesos dos índices oficiais. O universo amplo foi aproximado por volume anual de negociação, não reconstruído com as composições históricas oficiais do IBrX-100.

Por isso, a redução do diferencial observada com universos em pesos iguais é uma **comparação descritiva entre configurações**. Não é um percentual causal “explicado pela ponderação”, porque também há diferenças de seleção, composição, concentração e custos.

## Documentos

- [Histórico oficial ISE B3: anúncios, vigências e exclusões](https://iseb3.com.br/carteira-iseb3).
- [BDI 29/12/2022](https://arquivos.b3.com.br/bdi/download/bdi/2022-12-29/BDI_02_20221229.pdf).
- [BDI 02/01/2023](https://arquivos.b3.com.br/bdi/download/bdi/2023-01-02/BDI_02_20230102.pdf).
- [BDI 28/12/2023](https://arquivos.b3.com.br/bdi/download/bdi/2023-12-28/BDI_02_20231228.pdf).
- [BDI 30/12/2024](https://arquivos.b3.com.br/bdi/download/bdi/2024-12-30/BDI_02_20241230.pdf).
- [B3: novo calendário do ISE, Ofício 003/2024](https://www.b3.com.br/data/files/60/10/08/03/3F8FC8103152D4C8AC094EA8/OC%20003-2024-VPC%20Novo%20calendario%20da%20carteira%20do%20Indice%20de%20Sustentabilidade%20Empresarial%20da%20B3.pdf).
- [B3: mudança metodológica com vigência em janeiro de 2022, Ofício 005/2021](https://www.b3.com.br/data/files/F1/B0/1A/C2/365CA71068C61CA7AC094EA8/005-2021-VPC%20OC%20Revis%C3%A3o%20ISE%20v3_revCompliance_REVISADO_FORMATADO%20vDavi_RR%20vLimpa%20PT.pdf).
- [Metodologia IBrX-100](https://www.b3.com.br/data/files/CA/41/5A/43/96D947102255C247AC094EA8/IBXX-Metodologia-pt-br__Modelo_Novo_.pdf).

Cópias locais e hashes dos documentos obtidos estão em `dados/fontes/`.
