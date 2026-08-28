# Plano de trabalho do TCC

## 1. Corrigir a metodologia

- Verificar se o código está rebalanceando a carteira todos os dias. O
  trabalho informa que o rebalanceamento é anual.
- Usar apenas dados de P/VP e ROIC que já estavam disponíveis na data de
  formação da carteira.
- Calcular o momentum no fechamento e realizar a compra no pregão seguinte.
- Rever a estratégia multifatorial. Uma opção é usar um *score* combinado
  ou separar os fatores em quatro subcarteiras.
- Calcular o giro da carteira (*turnover*) e considerar os custos de
  negociação.

## 2. Melhorar a comparação das carteiras

- Aplicar a mesma estratégia fatorial ao IBrX-100. Isso ajuda a separar o
  efeito ESG dos demais fatores.
- Comparar carteiras com a mesma regra de ponderação.
- Explicar corretamente como o ISE B3 foi ponderado em cada período.

## 3. Rever os testes e as hipóteses

- Retirar a expressão “estatisticamente significativa” ou realizar um teste
  estatístico.
- Não afirmar que houve “não inferioridade” apenas comparando os índices de
  Sharpe. Essa conclusão exige um teste próprio.
- Substituir “prêmio ESG residual” por “retorno relativo da carteira”, a
  menos que seja estimado um alfa por regressão.

## 4. Apresentar melhor os resultados

- Incluir gráficos de patrimônio e *drawdown*.
- Mostrar os retornos de cada ano.
- Informar a composição das carteiras.
- Mostrar a distribuição por setor.
- Analisar separadamente a crise de 2020 e outros períodos de estresse.

## 5. Conferir o código e os dados

- Reproduzir a Tabela 1 diretamente pelo código.
- Conferir dados ausentes, empresas deslistadas e mudanças de ticker.
- Validar as composições históricas dos índices e das carteiras.
- Recalcular todas as métricas após as correções.

## 6. Ajustar as conclusões

- Evitar afirmações como “isolar”, “confirmar” e “rejeitar” sem testes que
  sustentem essas conclusões.
- Não afirmar que existe um “custo estrutural da restrição ESG”.
- Informar apenas que a carteira teve desempenho inferior dentro da amostra
  e da metodologia usadas.

## 7. Revisar a literatura

- Incluir outros estudos brasileiros sobre o ISE B3.

## Ordem de execução

1. Corrigir o código e os dados.
2. Refazer os cálculos.
3. Melhorar as comparações e os testes.
4. Criar as tabelas e os gráficos.
5. Ajustar as conclusões.
6. Revisar a literatura.
