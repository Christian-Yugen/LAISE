# M02-T003 — Spatial Separation & Near-Field 360

Preview e monitores concluídos. Critérios técnicos: **PASS**. Separação tridimensional e preferência perceptiva: **PENDENTES**.

## Comparação — 200–230 s

- [T001 preservada — referência](renders/comparison/M02_T003_T001_reference_200_230_level_matched_24bit.wav)
- [T002 preservada — referência](renders/comparison/M02_T003_T002_reference_200_230_level_matched_24bit.wav)
- [T003 — separação angular e near-field](renders/comparison/M02_T003_T003_near_field_200_230_level_matched_24bit.wav)

| Comparação | LUFS integrados | True peak dBTP | Correlação L/R |
|---|---:|---:|---:|
| T001_reference | -20.8 | -6.1 | 0.724 |
| T002_reference | -20.8 | -6.2 | 0.764 |
| T003_near_field | -20.8 | -6.3 | 0.746 |

Todas as versões musicais têm 30 s / 1.440.000 frames, estéreo PCM24 a 48 kHz. As cópias de referência recebem somente ganho vinculado para matching; os arquivos T001/T002 originais permanecem intactos. Não houve limiter, mastering ou render completo.

## Avaliar posições, não nomes de instrumentos

- [Monitor simplificado — mesmo som, oito direções e três alturas (27,5 s)](monitors/M02_T003_positions_same_sound_27_5s_24bit.wav)
- [Monitor simplificado — quatro fontes simultâneas (200–215 s)](monitors/M02_T003_four_positions_200_215_24bit.wav)
- [Percussion isolada — oito setores e volta completa (200–230 s)](monitors/M02_T003_percussion_eight_sectors_200_230_24bit.wav)

O primeiro monitor usa exatamente o mesmo trecho composto de Percussion, Woodwinds e Backing em todas as direções, sempre a 1 m. O composto é dual-mono apenas para esse diagnóstico, evita soma de canais em oposição de fase e recebe matching de nível. Assim, mudanças de instrumento ou distância não dão a resposta. Há 2 s de som e 0,5 s de pausa por posição.

A montagem diagnóstica tem organização temporal própria e fades de 20 ms nas bordas; nenhum original foi cortado ou alterado. O preview musical mantém os tempos absolutos. O monitor simultâneo preserva 200–215 s, usa quatro fontes a 1 m e menor densidade que a música.

Na primeira escuta, registre direção, altura e clareza antes de consultar a sequência esperada abaixo. Reconhecer o instrumento não faz parte do teste.

| Cue | Tempo no monitor | Direção esperada |
|---|---|---|
| D1 | 0.0–2.0 s | frente-direita |
| D2 | 2.5–4.5 s | direita |
| D3 | 5.0–7.0 s | trás-direita |
| D4 | 7.5–9.5 s | trás |
| D5 | 10.0–12.0 s | trás-esquerda |
| D6 | 12.5–14.5 s | esquerda |
| D7 | 15.0–17.0 s | frente-esquerda |
| D8 | 17.5–19.5 s | frente |
| H1 | 20.0–22.0 s | frente-baixo |
| H2 | 22.5–24.5 s | frente-altura normal |
| H3 | 25.0–27.0 s | frente-alto |

Monitor simultâneo: A frente-direita (45°/0°), B frente-esquerda (−45°/15°), C trás-esquerda (−135°/0°), D trás-direita elevada (135°/35°). Compare se percebe quatro posições/camadas, sem exigir quatro nomes.

## Cena próxima e separação

| Fonte | Posição de referência | Distância de referência | Intenção |
|---|---|---:|---|
| lead_vocal | 0° / 0° | 1.1 m | Âncora frontal, compactação candidata. |
| backing_vocals | -110° / 10° | 0.9 m | Lateral/traseira próxima, envolve sem tomar o centro. |
| woodwinds | -75° / 22° | 1.1 m | Travessias lateral/frontal expressivas, sem órbita completa. |
| drums | 18° / -20° | 1.2 m | Âncora frontal baixa, deslocamento angular moderado. |
| bass | 0° / -42° | 1.3 m | Âncora central baixa, separada da voz pela elevação. |
| guitar | -55° / 8° | 1.25 m | Faixa frontal esquerda. |
| keyboards | 55° / 15° | 1.3 m | Faixa frontal direita elevada. |
| percussion | 45° / -15° | 0.9 m | Órbita com oito setores; raio quase constante. |
| synth | 145° / 48° | 1.5 m | Camada traseira direita alta. |
| other | -155° / -5° | 1.6 m | Posição fixa, ganho conservador; identidade pendente. |
| brass | 120° / -35° | 0.85 m | Entradas pontuais em lados traseiros baixos. |

A maior parte da cena usa 0,85–1,6 m; Woodwinds tem aproximação pontual a 0,5 m e Backing a 0,6 m. Nenhuma fonte do preview vai além de 1,8 m. Azimute, frente/trás, elevação e trajetória são as pistas principais; a variação de raio é secundária.

Lead/Bass compartilham azimute central por função de âncora, mas diferem 42° em elevação. Drums permanece estável em 18°/−20°. Guitar e Keyboard ficam em lados frontais opostos. Other recebe faixa estática traseira esquerda e mantém ganho −4 dB; não se inferiu sua identidade nem se acrescentou movimento.

Lead e Percussion usam redução de Side a 50% antes do dearVR, com restauração RMS vinculada, como candidatos T003. Os demais stems mantêm imagem estéreo original. Não se adotou mono na música nem se alterou Stereo Width, Clarity, HRTF, reflection, reverb ou occlusion do plugin.

O controle de ganho por distância reutiliza a calibração medida na T002 e controla separadamente a loudness média de cada stem contra sua referência T001. A curva transferida é aproximada; o matching final limita confusão de volume médio. Loudness instantânea não é garantida idêntica.

## Órbita e movimento expressivo

Percussion inicia frente-direita em 45°, visita os oito setores e retorna em 405°, completando 360°. Cada setor tem pausa de 0,45 s, seguida de interpolação contínua. Raio 0,9 m e elevação −15° ficam constantes; profundidade não serve como pista para nomear o setor. O ciclo cobre aproximadamente 200,043–217,792 s.

| Setor | Tempo absoluto de chegada | Azimute desembrulhado |
|---|---:|---:|
| frente-direita | 200.043 s | 45° |
| direita | 202.261 s | 90° |
| trás-direita | 204.480 s | 135° |
| trás | 206.699 s | 180° |
| trás-esquerda | 208.917 s | 225° |
| esquerda | 211.136 s | 270° |
| frente-esquerda | 213.355 s | 315° |
| frente | 215.573 s | 360° |

Woodwinds percorre −75° → frente elevada → +75° na primeira frase (200–207,019 s), e a trajetória inversa na segunda (218,709–224,427 s). Assim, seu gesto frontal/lateral difere da órbita de Percussion. O ponto próximo ocorre na primeira frase; a elevação frontal distingue a passagem do centro vocal. Brass muda de lado nas pausas e fica parado durante os acentos.

## Validação e limites

- 46 WAVs verificados por hash, PCM24, 48 kHz, estéreo e frames exatos.
- Onze instâncias dearVR independentes, mesma janela 200–230 s, pre-roll comum de 1 s e mesma remoção de pre-roll; sem trimming por atividade.
- Sem NaN/Inf, clipping ou true peak inseguro. Continuidade de blocos e wrapping ±180° passaram nos critérios técnicos.
- Lead, Bass e Drums possuem poses constantes. Percussion tem 360° completos e oito eventos distintos; Woodwinds não faz uma órbita completa.
- Todos os arquivos anteriores MUSIC 02, incluindo T001/T002, e todos os arquivos Tukãna: SHA-256, tamanho e mtime preservados.
- Regressões da baseline T017 passaram; adapter, composer e pipelines aprovados permanecem intocados. Nenhum import de T018.

A auditoria de separação mede ângulos geométricos entre fontes ativas. Trajetórias contínuas cruzam temporariamente algumas faixas ocupadas; esses cruzamentos estão registrados, não escondidos. Distância angular nominal não equivale a direção percebida, e uma coordenada traseira pode continuar sendo ouvida como frontal conforme HRTF/ouvinte. O display de distância do plugin arredonda a 0,1 m.

O sucesso perceptivo depende de ouvir múltiplas fontes distintas, direções diferentes, frente/trás, altura, passagem ao redor da cabeça, proximidade, clareza e pouca confusão espacial. Um arquivo tecnicamente correto não prova esses resultados.

## Avaliação humana

Para cada comparação, registrar: número aproximado de posições distinguíveis; diferença frente/trás; altura; continuidade da volta; proximidade física; clareza; confusão; conforto. Depois indicar preferência T001/T002/T003. Nos monitores, registrar direções percebidas e quantidade de fontes, sem exigir identificação de instrumentos.

- [Cena independente do renderer](spatial_scenes/M02_T003_scene.json)
- [Relatório técnico, métricas e controles](reports/M02_T003_validation.json)
- [Auditoria angular entre fontes ativas](reports/angular_separation.json)
- [Cronograma e método dos monitores](reports/simplified_monitor.json)
- [Regressão dos arquivos exportados](reports/M02_T003_encoded_regression.json)

**Aguardar avaliação humana antes de prosseguir. Nenhum render completo ou mastering foi realizado.**
