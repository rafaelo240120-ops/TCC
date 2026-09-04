# Como o ISE B3 e o IBrX-100 são ponderados

> Plano de trabalho, item 2.3 — "Explicar corretamente como o ISE B3 foi
> ponderado em cada período".
>
> Todas as afirmações abaixo vêm dos documentos oficiais de metodologia da
> B3 / BM&FBOVESPA, citados ao final. Os trechos entre aspas são literais.

## Resumo

O ponto que o texto do TCC precisa incorporar é que **o ISE B3 não teve uma
regra única de ponderação no período 2016–2025**. Houve troca de regime a
partir da carteira de 2022, e a troca não foi só de fórmula: mudou também a
frequência de rebalanceamento. A série do ISE B3 usada como benchmark é,
portanto, a emenda de dois índices com construções diferentes.

| | ISE — carteiras 2006 a 2021 | ISE B3 — carteiras 2022 em diante | IBrX-100 — todo o período |
|---|---|---|---|
| **Peso do ativo** | valor de mercado do *free float* | **Score ISE B3** (desempenho ESG) | valor de mercado do *free float* |
| **Limites** | setor econômico ≤ 15% | ativo ≤ 3× o peso que teria por *free float*; empresa ≤ 10% | — (remete ao Manual) |
| **Vigência / rebalanceamento** | anual, do 1º dia útil de janeiro ao último de dezembro | seleção anual, **rebalanceamento quadrimestral** | **quadrimestral** (jan, mai, set) |
| **Universo elegível** | 200 maiores por Índice de Negociabilidade nos 12 meses anteriores; presença ≥ 50% | 200 maiores por IN nas 3 carteiras anteriores; presença ≥ 50% | 100 maiores por IN nas 3 carteiras anteriores; presença ≥ 95% |
| **Nº de ativos** | máximo 40 empresas | variável (69 na carteira de 2026) | 100 |
| **Tipo** | retorno total | retorno total | retorno total |

## 1. ISE — regime até a carteira de 2021

Metodologia BM&FBOVESPA, seção **F. Critério de Ponderação**:

> "O ISE medirá o retorno de uma carteira teórica composta pelos papéis que
> atenderem a todos os critérios discriminados anteriormente, ponderados pelo
> respectivo valor de mercado — no tipo pertencente à carteira — de suas ações
> disponíveis para negociação ('free float'), ou seja, serão excluídas as ações
> de propriedade do controlador."

E o único limite era setorial, não por empresa:

> "A participação de um setor econômico no ISE (considerando todos os tipos de
> ações das empresas incluídas, se for o caso) não poderá ser superior a 15%,
> quando das reavaliações periódicas."

Vigência (seção **E**):

> "A partir de 02 de janeiro de 2011, o período de vigência da carteira do ISE
> passou a ser do primeiro dia útil de janeiro ao último dia útil de dezembro
> de cada ano."

Ou seja: **carteira anual, peso por capitalização do free float**. É esse o
regime que vale para as carteiras de 2016 a 2021 do backtest.

## 2. ISE B3 — regime a partir da carteira de 2022

A B3 anunciou a nova metodologia em julho de 2021, válida para a formação da
carteira de 2022. Metodologia ISE B3 (jul/2021), seção **6. Critério de
Ponderação**:

> "Na carteira do ISE B3, os ativos são ponderados pelo Score ISE B3, com
> limite de participação baseado no valor de mercado do 'free float' (ativos
> que se encontram em circulação) da espécie pertencente à carteira."

> "A representatividade de um ativo no índice, quando dos rebalanceamentos
> periódicos, não poderá ser superior a 3 (três) vezes a participação que o
> ativo teria caso a carteira fosse ponderada pela representatividade do valor
> de mercado de 'free float' do ativo."

> "A participação de uma empresa no ISE B3 não poderá ser superior a 10% (dez
> por cento), quando de sua inclusão ou nos rebalanceamentos periódicos. Caso
> isso ocorra, serão efetuados ajustes para adequar o peso dos ativos das
> companhias a esse limite, redistribuindo-se o excedente proporcionalmente aos
> demais ativos da carteira."

O Score ISE B3 é o resultado do questionário (Score Base) ajustado pelo Fator
Qualitativo. A mesma metodologia introduziu **rebalanceamentos quadrimestrais**
(seções 4.6 e 5.1), contra a vigência anual do regime anterior.

Em uma frase: **o peso deixou de ser capitalização e passou a ser nota ESG**,
com a capitalização rebaixada ao papel de teto.

## 3. IBrX-100 — regra estável no período

Metodologia do Índice Brasil 100, seção **6. Critério de Ponderação**:

> "No IBrX 100, os ativos são ponderados pelo valor de mercado do 'free float'
> (ativos que se encontram em circulação) da espécie pertencente à carteira."

Seleção (4.1 e 4.2): 100 primeiros em ordem decrescente de Índice de
Negociabilidade no período de vigência das três carteiras anteriores, com
presença em pregão de 95%. Rebalanceamento quadrimestral.

## 4. Consequências para o trabalho

**(a) O benchmark ESG muda de natureza no meio da amostra.** De 2016 a 2021 o
ISE é um índice de capitalização restrito a empresas ESG; de 2022 em diante é
um índice *ponderado por nota ESG*. Atribuir o diferencial ISE − IBrX
integralmente a "restrição do universo investível" mistura dois efeitos:
a restrição de universo e a mudança de esquema de ponderação. A quebra deve
ser mencionada na seção de metodologia e nas limitações.

**(b) Comparar a carteira fatorial com os índices mistura ponderações.** A
carteira do TCC é de peso igual; os dois índices são ponderados por
capitalização (e, do ISE a partir de 2022, por score). Parte do diferencial é
puro efeito de ponderação — carteiras de peso igual têm viés de tamanho menor
e, no Brasil do período, isso não é neutro.

Por isso `src/comparacao_universos.py` calcula, além das carteiras fatoriais,
uma **carteira de peso igual com todo o universo elegível de cada índice**. A
comparação "peso igual contra peso igual" isola a restrição ESG da regra de
ponderação; a comparação contra os índices oficiais permanece como referência
do que um investidor de fato compraria.

**(c) A frequência de revisão também mudou.** O `universo_ise` do código lista
uma carteira por ano. Isso corresponde exatamente ao regime até 2021. De 2022
em diante existem três carteiras por ano (janeiro, maio e setembro), e a lista
anual passa a ser uma simplificação — as inclusões e exclusões de meio de ano
não são capturadas. É uma limitação a declarar, não um erro de cálculo: a
carteira do backtest é formada uma vez por ano por construção.

## Fontes

- B3. *Metodologia do Índice de Sustentabilidade Empresarial (ISE B3)*, julho/2021. [PDF](https://www.b3.com.br/data/files/DB/B2/66/3C/6B6AA71096B63AA7AC094EA8/ISE-Metodologia-pt-br%20vf.pdf)
- BM&FBOVESPA. *Índice de Sustentabilidade Empresarial (ISE) — Metodologia* (regime anterior). [PDF](https://assetfront.arquivosparceiros.cloud.itau.com.br/ITN/metodologia-do-indice-ISE.pdf)
- B3. *Metodologia do Índice Brasil 100 (IBrX 100)*. [PDF](https://www.b3.com.br/data/files/CA/41/5A/43/96D947102255C247AC094EA8/IBXX-Metodologia-pt-br__Modelo_Novo_.pdf)
- B3. *Índice de Sustentabilidade Empresarial (ISE B3)* — página do índice. [link](https://www.b3.com.br/pt_br/market-data-e-indices/indices/indices-de-sustentabilidade/indice-de-sustentabilidade-empresarial-ise-b3.htm)
- B3. *Índice Brasil 100 (IBrX 100 B3)* — página do índice. [link](https://www.b3.com.br/pt_br/market-data-e-indices/indices/indices-amplos/indice-brasil-100-ibrx-100.htm)
