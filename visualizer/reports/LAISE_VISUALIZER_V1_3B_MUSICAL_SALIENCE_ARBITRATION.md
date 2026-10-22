# LAISE Visualizer V1.3B — Musical Salience & Arbitration Engine

**PASS técnico — aguardar revisão humana da partitura intermediária.** Sem movimentos novos, sem ativação no runtime e sem commit/push/tag da V1.3B.

## Etapa 0: fundação congelada

V1.3A congelada no commit `50359f77e4d3dc63457caa6dc61b89ea0268555f`, tag anotada local `LAISE_VISUALIZER_V1_3A_APPROVED`. Antes do commit: 110 testes PASS, build PASS, diff check PASS, JSON da V1.3A idêntico nas duas análises, três capturas pixel-idênticas à V1.2 e playback real completo 10.282/10.282, sem dropped/duplicate/unexpected reset. Evidência: `v1_3a-musical-gesture-intelligence/freeze-checks.json`. A tag V1.2 continua no commit `6bc4b130f86356f0dd6994a55dfc91f4d78f7acb`.

Branch B: `feature/visualizer-v1.3b-musical-salience-arbitration`, criada a partir desse commit A. Nenhum push foi realizado. A V1.3A permanece uma fundação heurística e rastreável, não verdade musical absoluta.

## Arquitetura e causalidade

```text
V1.3A imutável: 12 fontes + 2.583 gestos + 10.282 ataques + features 20 ms + T007
  -> fusão de descrições primárias sobrepostas da MESMA fonte
  -> contexto / modificadores / reforços / continuidade / episódios independentes
  -> calibração robusta COMUM, intensidade absoluta preservada
  -> saliência multifatorial e arbitragem concorrente em janelas de 50 ms
  -> continuidade temporal e papéis evolutivos por fonte
  -> visual intent timeline OFFLINE (sem consumer no runtime)
```

Resultado: **505 intents**. Os 2.583 gestos continuam referenciados e todos os 10.282 ataques têm exatamente um intent proprietário. Fonte, timestamps, intensidade e posição T007 não são reescritos. Referências de contexto/modificação podem aparecer em vários intents, com interseções temporais explícitas; os ataques não são contabilizados duas vezes como drivers.

As bases são sustain, repetição ou impulso. Intervalos primários que se sobrepõem/tocam na mesma fonte formam um episódio contínuo. PHRASE é contexto e nunca cria um driver por si só. Crescendo/decrescendo modifica intensidade; movimento T007 modifica espaço; impulso interno é reforço; repetição interna mantém estrutura rítmica e todos os ataques. Um modificador sem base sobreposta pode originar um episódio evolving. Ataque sem base mantém um intent pontual causal, sem inventar duração ou confiança de classificação. Fontes diferentes nunca são fundidas.

PrimaryGesture é a descrição primária de maior duração; desempate por RMS absoluto e ID. É uma escolha de descrição do episódio, não prioridade de instrumento. Um sustain longo permanece contínuo, com roleSegments/evolutionRef; não é reiniciado a cada janela. As referências a sequências/roll/IOIs permanecem em rhythmicStructures, inclusive quando a base é sustentada. A futura resolução de polifonia interna a um stem não é alegada.

## Intensidade, calibração e distribuições

Definições separadas, por janela e por episódio:

- `absoluteIntensity`: RMS estéreo em full-scale na banda de análise V1.3A, sem ganho por fonte. Para intents compostos, RMS é medido nas features da fonte no intervalo; não é soma das intensidades de descrições sobrepostas.
- `sourceRelativeIntensity = I / P95_RMS_da_fonte`: somente diagnóstico. NÃO entra na fórmula de saliência, no ganho ou no visualEnergyCandidate.
- `trackRelativeIntensity = I / R`: escala comum robusta R = P95 dos frames RMS agrupados de todas as fontes. Pode ser >1; não há clamp que iguale eventos fortes.
- `localContextIntensity = I / sqrt(sum(I_fonte²))`: participação na norma energética do contexto, não loudness do master. Uma fonte fraca isolada pode ter contexto 1 sem aumentar seu RMS absoluto.
- `visualEnergyCandidate = (I/R)²`: candidato adimensional, monotônico em intensidade sob condições equivalentes. NÃO é Y, não altera ±2.8 nem propõe nova altura.

Referência comum RMS P95: `0.00535634855` FS. Referência flux P95: `8.935e-06`. Nenhum max(sample) ou true peak define a escala. `intensity-distributions.json` registra P50/P75/P90/P95/P99/MAX de RMS, intensidade de gesto, energia integrada e attack strength, globalmente e para cada fonte.

Energia/duração/peak/attack strength são auditados, mas não somados novamente ao RMS no score: são correlacionados ou favorecem duração/click isolado e poderiam duplicar energia. A energia integrada dos gestos sobrepostos é uma distribuição de descrições, não uma soma energética física da música. O RMS continua sendo o da análise 16 kHz da V1.3A; não é LUFS nem true peak nativo de 48 kHz.

## Fórmula, pesos e justificação

```text
A = log1p(I / R)
N = flux / (flux + P95_flux_global)
Q = densidade_de_ataques_250ms / (densidade_de_ataques_250ms + 4 Hz)
P = min(tempo_contínuo_relevante / 2 s, 1)
L = I / sqrt(sum(I_fonte²))
musicalSalience_raw = A * (1 + 0.15*N + 0.10*Q + 0.10*P + 0.10*L)
```

Flux é máximo dentro da janela; RMS usa média de potência das features originais na janela. Densidade conta somente os ataques originais da fonte, em intervalos semiabertos com bordas arredondadas a 1 µs para eliminar ambiguidades de ponto flutuante. A elegibilidade combina atividade medida pelo piso documentado da V1.3A com a presença de um episódio causal. Fora dela o score é zero, sem apagar os valores absolutos de auditoria.

Intensidade é a base comum. Novidade, ritmo, persistência e isolamento são medidos e oferecem apenas um bônus limitado: 1 ≤ fator ≤ 1,45. Assim, contexto não transforma uma fonte quase silenciosa em equivalente absoluto de uma fonte forte. Log1p preserva ordenação e reduz dependência de extremos sem saturar num teto rígido. Confidence NÃO é entrada na fórmula. Nenhum nome de instrumento, sourceClass ou prioridade fixa participa do cálculo.

Os pesos são heurísticos de engenharia, não estimados por experimento perceptual. A escolha é explicitamente auditável: bônus pequenos e não negativos preservam a base energética, fatores correlacionados não são somados duas vezes e a estabilidade local é testada. Isso NÃO prova que esses pesos sejam a única ou melhor definição de importância musical. O Q de 4 Hz é apenas uma referência suave comum, não tempo/compasso inferido.

## Continuidade e papéis concorrentes

Score filtrado com ataque exponencial τ=40 ms e release τ=120 ms; fonte inelegível sai sem ghost. Dominância admite conjuntos (empates de 1%), hysteresis 8%, hold mínimo 150 ms e bypass para mudança forte >1,5×. Papéis secondary e supporting usam razões ≥0,5 e ≥0,1 do maior score; o restante permanece background. Os thresholds são comuns às fontes. Não há top-K ou máximo fixo de instrumentos/dominantes. Doze fontes iguais podem ser co-dominantes, como o teste sintético demonstra.

Pequenas oscilações não trocam continuamente o dominante. Uma troca forte responde em até 150 ms no teste sintético; saliência filtrada não substitui os timestamps exatos de ataques. As janelas de 50 ms são análise offline, não agenda de playback. Nenhum smoothing do player, envelope físico ou tratamento de cues foi modificado.

Métricas da faixa: 1352 trocas do top raw e 739 mudanças do conjunto dominante filtrado. São proxies distintos (top único versus conjunto, com silêncio e empates); não se apresenta sua razão como uma medida perceptual exata de flicker. O teste G, com oscilações controladas, é a evidência isolada de estabilidade temporal.

## Sensibilidade e ablações

Cada um dos quatro pesos foi alterado individualmente em −20%, −10%, +10%, +20%: 16 análises. Limites declarados antes dos resultados: correlação média de ranks ≥0,95; Jaccard médio dos conjuntos dominantes ≥0,90; alteração P99 relativa de score ≤0,10.

Observado: menor correlação média **0.999882**; menor estabilidade de dominantes **0.988370**; maior alteração P99 **1.819%**. PASS. `sensitivity.json` contém todos os valores e limites. Ablações completas dos fatores também foram medidas, separadas do teste de pequenas perturbações:

| Fator removido | Jaccard dos dominantes |
|---|---:|
| novelty | 0.965542 |
| rhythm | 0.972560 |
| persistence | 0.982213 |
| isolation | 0.987154 |

A estabilidade é local aos pesos testados, não garantia para parâmetros arbitrários nem validação perceptual. Hold/τ/thresholds ainda são escolhas técnicas documentadas; não foram ajustados por instrumento.

## Concorrência e teste de caos

- Máximos observados: **12 fontes**, **35 descrições de gesto**, **12 intents** e **3 dominantes**.
- Média em janelas relevantes: 16.325 descrições versus 7.119 drivers; redundância integrada reduzida **56.39%**.
- Dominantes por janela relevante: média 1.030. Nenhum limite de três foi imposto: esse máximo é resultado dos dados.
- Proxies por janela incluem activeSources, activeGestures, activeVisualIntents, dominantCount e distribuição de saliência. Os 20 piores frames por concorrência estão em analysis-summary.json.
- A redução é de descrições redundantes, NÃO de música: todos os gestos continuam referenciados e cada ataque tem um único proprietário. Esses proxies NÃO provam legibilidade de ondas futuras, pois nenhum desenho/behavior engine foi criado.

## Resultados por fonte

| Fonte | Intents | Atividade s | Dominância s | RMS P95 absoluto | Saliência média |
|---|---:|---:|---:|---:|---:|
| backing_vocals | 69 | 214.70 | 93.55 | 0.00913215 | 0.453641 |
| bass | 46 | 211.25 | 10.15 | 0.00447993 | 0.293133 |
| brass | 29 | 124.40 | 0.40 | 0.00001970 | 0.002032 |
| drums | 63 | 253.25 | 46.10 | 0.00663193 | 0.439761 |
| guitar | 12 | 82.65 | 0.00 | 0.00049044 | 0.018062 |
| keyboards | 19 | 222.50 | 0.00 | 0.00061288 | 0.040161 |
| lead_vocal | 43 | 269.75 | 76.80 | 0.00603672 | 0.443405 |
| other | 17 | 280.70 | 3.55 | 0.00147686 | 0.128085 |
| percussion | 81 | 249.55 | 57.20 | 0.00799818 | 0.467940 |
| strings | 31 | 131.10 | 0.00 | 0.00038827 | 0.015483 |
| synth | 41 | 264.05 | 19.50 | 0.00377882 | 0.269756 |
| woodwinds | 54 | 82.65 | 31.45 | 0.00464646 | 0.128001 |

As durações por papel completas estão em analysis-summary.json. Background também inclui janelas inativas; não significa que a fonte soou durante toda essa duração. Uma fonte pode não dominar esta gravação sem haver bloqueio por identidade; testes de permutação e Strings forte/Drums fracos cobrem essa independência.

## Casos sintéticos A–G e contratos

- A: uma fonte forte e onze fracas → forte dominante.
- B: duas fontes equivalentes → ambas co-dominantes, sem desaparecimento arbitrário.
- C: sustain com ataques pequenos internos → um episódio contínuo, ataques como reforços.
- D: crescendo dentro do sustain → modificador, não segundo driver.
- E: fraca isolada → pode dominar o contexto sem alteração no RMS/score absoluto.
- F: troca forte → resposta rápida, ≤150 ms no caso controlado.
- G: pequenas oscilações → no máximo uma mudança inicial de conjunto, sem flicker sucessivo.
- Contratos adicionais: troca de nomes/colunas não altera scores, monotonicidade, confidence independente, PHRASE não-driver, fonte nunca fundida com outra, proprietário único em bordas, robustez a click extremo, ausência de top-K e ghost no silêncio, intervalos exatos de densidade, preservação das features e referências, esquema e rejeição de corrupção.
- Evidência numérica A–G em synthetic-cases.json: troca forte medida em 0.050 s; pequenas oscilações produziram 1 mudanças do conjunto dominante em 100 frames.

## Casos reais e revisão independente

| Região | Tempo selecionado s | Gestos | Intents | Dominantes | Fonte de maior score |
|---|---:|---:|---:|---:|---|
| dense | 124.75 | 35 | 12 | 1 | percussion |
| quiet | 329.90 | 0 | 0 | 1 | brass |
| percussion | 278.05 | 26 | 11 | 1 | percussion |
| bass-dense | 86.60 | 15 | 6 | 1 | drums |
| strings | 272.35 | 20 | 8 | 1 | percussion |
| synth | 264.55 | 13 | 5 | 1 | synth |
| vocal-sustain | 226.95 | 23 | 11 | 1 | backing_vocals |
| crescendo | 77.00 | 16 | 6 | 1 | bass |
| decrescendo | 327.10 | 20 | 7 | 1 | percussion |
| roll | 57.90 | 19 | 9 | 1 | percussion |

Índice offline: `v1_3b-musical-salience-arbitration/index.html`. O inspector possui dados embutidos, funciona sem fetch e mostra, em qualquer janela, 12 fontes, intensidade absoluta/relativas, score e papel. Clique numa fonte para seguir intent → gestos → ataques. Os IDs/refs têm sua fonte T007 no artefato; os dados espaciais não são recalculados nem alterados.

SVGs: `timelines/overview-0-330.svg`, 11 zooms de 30 s e casos direcionados de densidade, silêncio, Percussion forte, Bass denso, sustain vocal, Strings, Synth, crescendo, decrescendo e roll. A visão completa mostra gestos A, intents B, RMS comum, score comum, valores relativos apenas diagnósticos e dominância evolutiva. Hover preserva IDs e intervalos. `cases-real.json` contém rankings e refs das regiões selecionadas automaticamente.

Página testada tanto pelo servidor local quanto como arquivo standalone: 12 fontes presentes, slider temporal, clique de rastreabilidade por fonte e links PASS, sem erros de JavaScript. Visão completa e casos denso/roll/silencioso foram renderizados e inspecionados. Evidência: visual-audit-checks.json e PNGs de QA; não são capturas de uma alteração do produto.

## Determinismo, hashes e regressões

Duas análises completas independentes: JSON principal byte-idêntico, SHA-256 `4c42dbaceb0adcd7010a1981186e8e75a11e03539ef4e90634ebc690d98add7b`. analysis-summary, sensitivity e intensity-distributions também são byte-idênticos. Não há seed variável, timestamp, hostname ou caminho absoluto no novo artefato. Toda ordenação e desempate são explícitos.

- Testes: **138 PASS**, sendo 110 anteriores e 28 novos. Nenhum teste anterior foi removido/enfraquecido.
- Build produção PASS; persiste apenas o aviso conhecido de bundle >500 kB. diff check PASS.
- Playback real integral: **10.282/10.282 únicos**, zero dropped/duplicate/unexpected reset, sem erros de console/mídia.
- Capturas 0/46,5/200,5 s: PNGs byte-idênticos à V1.2, portanto pixel-idênticos.
- 79200 linhas de score recalculadas independentemente da serialização; erro máximo 6.24390761e-10, tolerância 1e-8.
- Todos os hashes dos 12 WAVs, master, cues, T007, V1.3A e features conferidos; nenhum desses dados foi alterado. Nenhuma referência da tag V1.2 foi movida.

| Artefato/entrada | SHA-256 |
|---|---|
| analyzer | `bd2f5cd04a96930d360bb67dcde661f15d9c0650c25efe3d26639726a44de01e` |
| builder | `5d240537805dcfc83cb4934ea0b9a3d86f2a1fffa92463d7e0bc7faa22750212` |
| cueDataset | `c880676240a480f72cf3dc42fc5b3a656bd38fd466a79474698abd81b99e944c` |
| gesturesV13A | `6c2c0796fd42dc178f7211061b3b5a75fad412b9e8e5a7324b8db4a1f6c8dc54` |
| master | `4f4d46a870faf29fa51867450a5a70cc82faad1b863d83bd40e89c6d27a3e271` |
| t007Automation | `954b82b30ace79356dc31284891e561554b9b4eb67cc26386212f94b54e94792` |

## Limitações e estado final

Saliência é um modelo heurístico auditável, não leitura absoluta de intenção musical. Os stems podem conter processamento, vazamento e polifonia; a fusão por fonte não separa notas/vozes simultâneas internas. O bônus limitado pode não reproduzir toda percepção humana de conteúdo fraco mas semanticamente crucial. Os pesos/thresholds necessitam revisão humana. Classificação V1.3A e seus possíveis falsos positivos são preservados como evidência, não promovidos a certeza.

Uma descrição pode cruzar vários episódios: suas interseções são modificadores/contexto e sua duração original continua no dataset A. O intent não inventa uma onda para cada descrição. Valores relativos por stem podem ser altos em Brass fraco, mas nunca entram como ganho. A análise em 50 ms agrega concorrência dentro da janela; intents pontuais mantêm seus tempos exatos e a futura execução não deverá usar essa grade como substituto dos cues.

O artefato público é um recurso offline adicional, não baixado pelo runtime. O build o copia como asset, aumentando o volume estático disponível; nenhuma carga DSP foi adicionada ao navegador principal. Não se implementou headroom dinâmico, altura Y, novas ondas, interferência, prioridade por instrumento, saliência no renderer ou V1.3C.

Reprodução a partir de visualizer:
```powershell
python -B tools/build_musical_visual_intents.py
python -B tools/render_musical_salience.py
python -B tools/validate_musical_salience.py
node --test tests/*.test.js
python -B -m unittest discover -s tests -p "test_*.py"
npm run build
```

Relatório sustentado por `final-checks.json`, `sanity-checks.json`, `determinism.json`, `sensitivity.json`, `cases-real.json`, `pixel-regression.json`, `real-run-v13b.json` e logs em `visualizer/reports/v1_3b-musical-salience-arbitration/`.

**Aguardar revisão humana. A V1.3B permanece sem commit, push ou tag.**
