# LAISE Visualizer V1.3A — Musical Gesture Intelligence Foundation

**PASS técnico — aguardando revisão humana da análise e das classificações.** Nenhum novo comportamento visual, amplitude ou física foi implementado. Sem commit, push, merge ou tag.

## Baseline e arquitetura

Branch `feature/visualizer-v1.3-musical-gesture-engine`, criada diretamente da tag `LAISE_VISUALIZER_V1_2_APPROVED`, no commit `6bc4b130f86356f0dd6994a55dfc91f4d78f7acb`. A branch V1.3 anteriormente publicada não foi modificada. Os hashes protegidos e o diff de toda a produção V1.2 foram reconferidos: idênticos.

```text
12 WAVs espaciais T007 + automação T007 + cues V1.2 imutáveis
  -> DSP offline por stem (sem misturar identidades)
  -> features absolutas + regras temporais/espectrais explícitas
  -> ataques referenciados + gestos + relações + trajetórias
  -> public/audio/tukana-musical-gestures-v1.json
  -> SVGs/JSONs de auditoria; NÃO conectado ao runtime
```

O browser continua consumindo somente os cues V1.2. O novo arquivo não é importado ou buscado pelo player. Não houve alteração em Spatial Field, câmera, HUD, controles, domínio 16×16, grid 128×128, yaw, RippleField, motionGain, T007, cores, glow, bloom, partículas ou master.

## Metodologia e features

Os 12 WAVs T007 são verificados contra os hashes armazenados nos cues aprovados. FFmpeg faz apenas decodificação e resampling técnico para 16 kHz estéreo; nenhum WAV é regravado, amplificado ou normalizado. A identidade e os índices dos 10.282 cues existentes são preservados. A análise NÃO tenta gerar uma nova verdade de onset nem recuperar ataques filtrados na V1.2.

| Feature | Unidade/método | Função mensurável |
|---|---|---|
| RMS/envelope | RMS estéreo de potência, janela centrada 64 ms, hop 20 ms; média 100 ms | energia absoluta, atividade e sustentação |
| Peak local / crest factor | peak do sinal reamostrado; peak/RMS | distribuição robusta para futura V1.3B; não é true peak nem regra de altura |
| Energia integrada | soma RMS² × hop; aproximação energética por janela | duração versus intensidade; pooled por fonte, não loudness do master |
| Flux espectral | diferenças positivas de magnitude FFT, sem normalização por fonte | evidência de novidade e futura inspeção de ataques |
| Centroide e flatness espectral | Hz; flatness de potência | hipótese de tom estável versus textura; não transcrição de pitch |
| IOI / variância / CV / correlação | intervalos dos cues da MESMA fonte | regularidade, aceleração, desaceleração e densidade |
| Tendência energética | correlação tempo × log-RMS, diferença em dB entre quintis | crescendo/decrescendo consistente, rejeitando flutuação pequena |
| timeToRmsPeak / timeAfterRmsPeak | segundos dentro do gesto | localização mensurada do pico; não estimativa precisa de ADSR de uma nota |
| sustainAboveActivityFloorSeconds | energia acima do piso após 150 ms | suporte temporal real, distinto do comprimento total do gesto |
| T007 | ângulo unwrapped, elevação, distância e X/Z originais | trajetória com causa espacial conhecida durante energia ativa |

Zero crossings não foram acrescentados: não sustentam uma decisão adicional confiável neste material polifônico. A intensidade de cada gesto é RMS absoluto; attackStrength mantém o RMS original dos cues; sustainStrength é RMS posterior a 150 ms. Não há novo Dynamic Visual Headroom, teto de altura ou normalização relativa por stem.

## Taxonomia, regras e thresholds

| Tipo | Evidência exigida / limite |
|---|---|
| IMPULSE | envelope retorna a 25% do pico local ou piso em 20–350 ms; referência ao ataque preservada |
| REPEATED_PULSE / SEQUENCE | 2–3 / >=4 ataques; CV IOI <=0,18, janela <=8 s, gaps <=1,25 s; par exige IOI 0,12–1,25 s |
| ACCELERATING / DECELERATING | >=4 ataques, correlação IOI × índice >=0,65 em módulo e razão entre terços >=1,3 |
| TREMOLO_OR_ROLL | >=6 ataques, >=8 Hz, CV <=0,35; busca local <=2 s, gaps <=0,18 s e contraste RMS mediano dentro dos IOIs >=15% |
| SUSTAINED_TONE / TEXTURE | energia contínua >=0,6 s; furos internos <=120 ms; cortes explícitos a cada 8 s; tom: flatness <0,08 e CV centroide <0,35 |
| CRESCENDO / DECRESCENDO | janela >=2 s, suporte ativo >=90%, variação >=6 dB e correlação absoluta >=0,8; união somente se a regra continuar válida |
| PHRASE | agrupamento temporal da MESMA fonte; gap >1,4 s delimita; limite operacional 12 s |
| CONTINUOUS_MOTION | energia sustentada + variação T007 >=10° azimute ou >=5° elevação ou >=0,15 m distância |
| TRANSITION | não inferido: não há modelo validado de mudança de seção/harmonia; não inventar exemplos |

O piso de atividade é max(1e-6, 0,06×P95 do envelope por fonte). É somente um critério reversível de segmentação: os valores de áudio/energia/intensidade permanecem absolutos, e o piso usado é registrado em cada estatística. Não aumenta stems fracos. Para ruído, caudas HRTF e fontes muito baixas, o piso pode influenciar a divisão de regiões e precisa de revisão.

## Hierarquia e identidade

Os ataques são referências estáveis `index` para o dataset V1.2 e mantêm source/time/amplitude/strength originais. Relações `containsAttack` ligam gestos a ataques; `containsGesture` liga uma PHRASE a gestos totalmente contidos da mesma fonte. Toda referência de ataque pertence à mesma fonte do gesto, sem mistura entre Drums/Percussion/Bass/vozes. Todos os 10.282 ataques pertencem a ao menos uma frase temporal. Não existe ciclo: frases são os únicos pais de gestos e não são filhas de outras frases.

As camadas podem se sobrepor: uma frase pode conter uma sequência, energia sustentada e uma tendência. Isso não significa movimentos simultâneos futuros. Deduplicação semântica, arbitragem de saliência e interação entre fontes NÃO são executadas nesta fase. Nenhuma análise desta fase exige escolher entre um grupo e seus ataques constituintes.

## Confidence e ambiguidades

Confidence é um score heurístico de suporte da regra, não probabilidade calibrada: impulso 0,80; sustain espectral 0,72; frase temporal 0,60; movimento conhecido T007 0,95; repetição/tendência variam conforme regularidade/correlação, com tetos 0,85–0,95. Os valores não foram validados contra anotação humana. Alto score de periodicidade prova regularidade do detector, não garante interpretação musical de compasso ou técnica.

Tom sustentado pode ser harmônico/polifônico ou ressonância de percussão; textura não significa instrumento específico. Tremolo/roll é candidato de ataques densos e regulares, sem certeza de técnica instrumental. Crescendos podem refletir execução, automação e processamento espacial do stem; não se atribui intenção expressiva apenas pela curva. PHRASE é proxy de gaps e cortes operacionais, não teoria musical completa. Os cortes de 8/12 s são artefatos declarados de segmentação.

A inspeção gráfica inicial identificou uma sequência densa de Bass com envelope relativamente contínuo. O detector foi corrigido para não tratar timestamps próximos como prova suficiente de roll: agora exige contraste RMS mediano >=15% dentro dos intervalos. Sequências densas sem modulação suficiente ficam somente como REPEATED_PULSE_SEQUENCE com confidence 0,55 e limitação explícita. O teste de tom contínuo com cues densos rejeita roll. Mesmo com modulação, roll/tremolo continua hipótese de estrutura, não técnica instrumental comprovada.

Uma faixa fraca pode apresentar sustain sem cue inicial: isso é permitido e documentado, com attackRefs vazio. Não se inventa ataque para completar um gesto. A separação dos stems e a automação T007 são fontes de verdade de identidade/posição, não reconstrução binaural a partir de stereo. A lei de legibilidade não pode ser provada por esta camada analítica; será uma restrição obrigatória do futuro behavior engine.

## Resultados por stem

| Stem | Ataques preservados | Gestos | Duração média s | RMS P50 / P95 / MAX | Confidence média |
|---|---:|---:|---:|---|---:|
| lead_vocal | 935 | 161 | 3.753 | 0.001958 / 0.006037 / 0.009762 | 0.760 |
| backing_vocals | 819 | 190 | 2.439 | 0.001415 / 0.009132 / 0.015421 | 0.760 |
| drums | 1410 | 594 | 1.092 | 0.001344 / 0.006632 / 0.015265 | 0.784 |
| bass | 1496 | 359 | 1.446 | 0.001126 / 0.004480 / 0.009404 | 0.772 |
| guitar | 386 | 57 | 3.035 | 0.000005 / 0.000490 / 0.003286 | 0.749 |
| keyboards | 941 | 93 | 5.148 | 0.000092 / 0.000613 / 0.001818 | 0.747 |
| percussion | 1524 | 554 | 1.118 | 0.001400 / 0.007998 / 0.017292 | 0.781 |
| strings | 213 | 100 | 2.092 | 0.000011 / 0.000388 / 0.002393 | 0.766 |
| synth | 1262 | 174 | 3.364 | 0.000978 / 0.003779 / 0.009338 | 0.757 |
| other | 859 | 127 | 4.692 | 0.000487 / 0.001477 / 0.010428 | 0.752 |
| brass | 11 | 52 | 2.535 | 0.000000 / 0.000020 / 0.001692 | 0.761 |
| woodwinds | 426 | 122 | 1.860 | 0.000004 / 0.004646 / 0.012263 | 0.785 |

Total: **2583 gestos**, **26577 relações**, 12 fontes e 10.282 ataques preservados. P50/P75/P90/P95/P99/MAX de RMS, peak e intensidade de gesto estão em `analysis-summary.json`, por fonte e globalmente. As distribuições globais agrupam observações por fonte; não representam soma acústica ou LUFS do master.

| Tipo | Quantidade |
|---|---:|
| ACCELERATING_SEQUENCE | 13 |
| CONTINUOUS_MOTION | 17 |
| CRESCENDO | 58 |
| DECELERATING_SEQUENCE | 6 |
| DECRESCENDO | 87 |
| IMPULSE | 1555 |
| PHRASE | 293 |
| REPEATED_PULSE | 19 |
| REPEATED_PULSE_SEQUENCE | 18 |
| SUSTAINED_TEXTURE | 122 |
| SUSTAINED_TONE | 316 |
| TRANSITION | 0 |
| TREMOLO_OR_ROLL | 79 |

Distribuição por tipo e stem:

- **lead_vocal:** ACCELERATING_SEQUENCE=3, CONTINUOUS_MOTION=1, CRESCENDO=10, DECRESCENDO=13, IMPULSE=60, PHRASE=30, REPEATED_PULSE=1, REPEATED_PULSE_SEQUENCE=1, SUSTAINED_TEXTURE=5, SUSTAINED_TONE=37
- **backing_vocals:** ACCELERATING_SEQUENCE=2, CRESCENDO=4, DECELERATING_SEQUENCE=1, DECRESCENDO=8, IMPULSE=102, PHRASE=29, REPEATED_PULSE=2, SUSTAINED_TEXTURE=1, SUSTAINED_TONE=41
- **drums:** ACCELERATING_SEQUENCE=1, CRESCENDO=2, DECELERATING_SEQUENCE=2, DECRESCENDO=4, IMPULSE=491, PHRASE=30, SUSTAINED_TEXTURE=14, SUSTAINED_TONE=33, TREMOLO_OR_ROLL=17
- **bass:** ACCELERATING_SEQUENCE=2, DECRESCENDO=3, IMPULSE=237, PHRASE=33, REPEATED_PULSE=1, REPEATED_PULSE_SEQUENCE=1, SUSTAINED_TEXTURE=29, SUSTAINED_TONE=10, TREMOLO_OR_ROLL=43
- **guitar:** ACCELERATING_SEQUENCE=1, CONTINUOUS_MOTION=1, CRESCENDO=2, DECRESCENDO=3, IMPULSE=17, PHRASE=13, REPEATED_PULSE=1, REPEATED_PULSE_SEQUENCE=3, SUSTAINED_TEXTURE=4, SUSTAINED_TONE=12
- **keyboards:** CRESCENDO=7, DECRESCENDO=7, IMPULSE=8, PHRASE=22, REPEATED_PULSE=1, REPEATED_PULSE_SEQUENCE=10, SUSTAINED_TEXTURE=20, SUSTAINED_TONE=18
- **percussion:** CRESCENDO=2, DECELERATING_SEQUENCE=1, DECRESCENDO=2, IMPULSE=448, PHRASE=36, REPEATED_PULSE=2, SUSTAINED_TEXTURE=19, SUSTAINED_TONE=25, TREMOLO_OR_ROLL=19
- **strings:** ACCELERATING_SEQUENCE=1, CONTINUOUS_MOTION=5, CRESCENDO=4, DECRESCENDO=7, IMPULSE=33, PHRASE=12, REPEATED_PULSE_SEQUENCE=1, SUSTAINED_TEXTURE=1, SUSTAINED_TONE=36
- **synth:** ACCELERATING_SEQUENCE=1, CRESCENDO=9, DECRESCENDO=13, IMPULSE=70, PHRASE=35, REPEATED_PULSE=3, REPEATED_PULSE_SEQUENCE=1, SUSTAINED_TEXTURE=5, SUSTAINED_TONE=37
- **other:** ACCELERATING_SEQUENCE=2, CRESCENDO=11, DECELERATING_SEQUENCE=1, DECRESCENDO=20, IMPULSE=10, PHRASE=35, REPEATED_PULSE=5, SUSTAINED_TEXTURE=16, SUSTAINED_TONE=27
- **brass:** CONTINUOUS_MOTION=5, CRESCENDO=4, DECELERATING_SEQUENCE=1, DECRESCENDO=1, IMPULSE=3, PHRASE=4, REPEATED_PULSE_SEQUENCE=1, SUSTAINED_TEXTURE=8, SUSTAINED_TONE=25
- **woodwinds:** CONTINUOUS_MOTION=5, CRESCENDO=3, DECRESCENDO=6, IMPULSE=76, PHRASE=14, REPEATED_PULSE=3, SUSTAINED_TONE=15

## Exemplos reais selecionados automaticamente

| Tipo | Stem | Início–fim s | Confidence | RMS absoluto | Ataques |
|---|---|---|---:|---:|
| IMPULSE | percussion | 242.520–242.820 | 0.800 | 0.011412 | 1 |
| REPEATED_PULSE_SEQUENCE | keyboards | 124.752–125.312 | 0.890 | 0.000317 | 5 |
| SUSTAINED_TONE | backing_vocals | 166.200–174.200 | 0.720 | 0.007767 | 31 |
| CRESCENDO | other | 75.000–77.000 | 0.940 | 0.000313 | 6 |
| DECRESCENDO | keyboards | 327.000–329.000 | 0.947 | 0.000287 | 2 |
| TREMOLO_OR_ROLL | drums | 57.632–58.256 | 0.828 | 0.003434 | 8 |

`cases.json` contém as features, índices de ataques, evidências e trajetórias completas de cada exemplo. A seleção usa maior confidence, desempate por intensidade RMS absoluta, número de ataques, tempo e fonte; nenhum exemplo é inventado.

## Espaço, determinismo e sanity

27559 amostras espaciais conferidas contra o interpolador T007 original, tolerância 2e-5, erro máximo observado 4.99772627e-07. Cada gesto inclui início/pico/fim e amostras a cada 250 ms, mais os knots de automação internos. Azimute permanece unwrapped; repetir um tempo de automação mantém a última chave, conforme o mapping aprovado. Elevação, distância e X/Z são preservados numericamente, sem novo mapeamento para a malha.

Duas análises completas independentes dos 12 WAVs geraram JSON **byte-idêntico**, SHA-256 `6c2c0796fd42dc178f7211061b3b5a75fad412b9e8e5a7324b8db4a1f6c8dc54`. As 12 séries de features também são byte-idênticas. Não há seed aleatória, timestamp de geração ou caminho absoluto de máquina no artefato. Ambiente/versões são registrados; determinismo entre versões diferentes de FFmpeg/NumPy não é alegado.

Sanity PASS: schema, fontes válidas, IDs únicos, start<=peak<=end, duração, ordenação, finitude recursiva, confidence [0,1], referências íntegras e espaço dentro dos limites. Artefato complementar criado sem substituir cues.

## Regressão V1.2 e testes

- 82 testes anteriores PASS; 28 novos testes PASS; **110 testes no total**.
- Novos testes cobrem DSP determinístico, RMS estéreo antifase, relações absolutas de intensidade, schema, ordem, fontes, hierarquia, repetição, aceleração/desaceleração, roll local, sustentação/impulso, tendências e rejeição de pequenas flutuações, confidence, interpolação espacial, source hashes e referências.
- Playback real integral 330 s: **10.282/10.282**, 10.282 únicos, zero dropped/duplicate/unexpected reset; sem erro de console/mídia.
- Capturas 0 / 46,5 / 200,5 s: PNGs byte-idênticos à baseline V1.2, portanto pixel-idênticos.
- Build produção PASS; permanece o aviso histórico de bundle >500 kB. git diff --check PASS.
- Nenhum teste anterior foi removido ou alterado. Nenhum código de produção foi alterado.

## Evidências e reprodução

- Artefato: `visualizer/public/audio/tukana-musical-gestures-v1.json`.
- Índice visual: `visualizer/reports/v1_3a-musical-gesture-intelligence/index.html`.
- Visão 330 s: `timelines/overview-0-330.svg`; 11 zooms: `timelines/zoom-000-030.svg` até `zoom-300-330.svg`.
- Gráficos dos casos encontrados: `timelines/case-*.svg`; dados completos: `cases.json`; espaço T007 por stem: `timelines/spatial-trajectories.svg`.
- Features temporais absolutas por stem: `features/*.json` (20 ms).
- `determinism.json`, `sanity-checks.json`, `final-checks.json`, `pixel-regression.json`, `real-run-v13a.json` e logs preservam as verificações.
- Scripts em `visualizer/tools`: `build_musical_gestures.py`, `musical_gestures.py`, `render_musical_gestures.py`, `validate_musical_gestures.py`, `validate_gesture_v12_regression.py`.

```powershell
cd visualizer
python -B tools/build_musical_gestures.py
python -B tools/render_musical_gestures.py
python -B tools/validate_musical_gestures.py
node --test tests/*.test.js
python -B -m unittest discover -s tests -p "test_*.py"
npm run build
```

## Hashes de proveniência

| Entrada/analisador | SHA-256 |
|---|---|
| analyzer | `80d4e17206a7f5dea0aaa3f6e19b5de7248b3653e02aeabe79c148114d143696` |
| builder | `141cfab1055b5c892335cb404d082d31fe19ccb1ff8018800a25de1045978c00` |
| cueDataset | `c880676240a480f72cf3dc42fc5b3a656bd38fd466a79474698abd81b99e944c` |
| master | `4f4d46a870faf29fa51867450a5a70cc82faad1b863d83bd40e89c6d27a3e271` |
| t007Automation | `954b82b30ace79356dc31284891e561554b9b4eb67cc26386212f94b54e94792` |
| stem backing_vocals | `bb7a939faf9c06fb038cf7d527e4bd706a452ccc4badad101992881acdce0b0c` |
| stem bass | `81a9aea0f6422b1eec22a5f233e18c5c49b8867dee8427d0cc63c6437ab77729` |
| stem brass | `409d483e7fa324f981b0050dd0139b2971730a9485ff4883489c4d162ff916a3` |
| stem drums | `d55661dc3b868a5919eacf4a1e91dc8e767e6f4137f24487b865478f89ede20f` |
| stem guitar | `80aa059c8d210ba3360c3589765d367eb7a42600b63f717180cf099b7663d401` |
| stem keyboards | `553b0c333f2eb6e6eb738df4230be0703c613b4ad50b05e72ab0848cadcfca2a` |
| stem lead_vocal | `b4c762a601586d214cec589a196ce1991c6c6703416be30e4d4073d243cca435` |
| stem other | `ce118a63cd155756bc0a4a8eab5741f702605b619338d274eb75f03e9cd19d94` |
| stem percussion | `6abeb7ad3e1158077b13c88cbdf52a66ff7a85448d2f9b7ea0c09d449b0fa07c` |
| stem strings | `8870e111a31b5aa541072390e3c1b961c44a71ea5eced429c8b22c858f138d30` |
| stem synth | `9537fed481a0ff1f8978461b4943bc71e19519f1a56265410d4fdf759615ea6a` |
| stem woodwinds | `b471570c1777fa3b475a4a9fb2908476f0f8e07372439a8633211317bac2d11a` |

**Conclusão:** fundação analítica concluída, com classificação heurística revisável e rastreável. Aguardar revisão humana dos gráficos e dos casos. Não iniciar V1.3B, headroom, saliência ou comportamentos visuais nesta fase.
