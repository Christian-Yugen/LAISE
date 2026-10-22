"""Build review report from actual outputs; refuses PASS without all evidence."""
from pathlib import Path
import json
V=Path(__file__).resolve().parents[1];OUT=V/'reports/v1_3a-musical-gesture-intelligence'
def main():
 load=lambda p:json.loads(p.read_text(encoding='utf-8'))
 d=load(V/'public/audio/tukana-musical-gestures-v1.json');det=load(OUT/'determinism.json');sanity=load(OUT/'sanity-checks.json');checks=load(OUT/'final-checks.json');live=load(OUT/'real-run-v13a.json');pixels=load(OUT/'pixel-regression.json');cases=load(OUT/'cases.json')
 assert det['pass'] and sanity['pass'] and checks['pass'] and live['pass'] and all(p['pixelIdentical'] for p in pixels)
 lines=['# LAISE Visualizer V1.3A — Musical Gesture Intelligence Foundation','', '**PASS técnico — aguardando revisão humana da análise e das classificações.** Nenhum novo comportamento visual, amplitude ou física foi implementado. Sem commit, push, merge ou tag.','',
 '## Baseline e arquitetura','',
 'Branch `feature/visualizer-v1.3-musical-gesture-engine`, criada diretamente da tag `LAISE_VISUALIZER_V1_2_APPROVED`, no commit `6bc4b130f86356f0dd6994a55dfc91f4d78f7acb`. A branch V1.3 anteriormente publicada não foi modificada. Os hashes protegidos e o diff de toda a produção V1.2 foram reconferidos: idênticos.','',
 '```text','12 WAVs espaciais T007 + automação T007 + cues V1.2 imutáveis','  -> DSP offline por stem (sem misturar identidades)','  -> features absolutas + regras temporais/espectrais explícitas','  -> ataques referenciados + gestos + relações + trajetórias','  -> public/audio/tukana-musical-gestures-v1.json','  -> SVGs/JSONs de auditoria; NÃO conectado ao runtime','```','',
 'O browser continua consumindo somente os cues V1.2. O novo arquivo não é importado ou buscado pelo player. Não houve alteração em Spatial Field, câmera, HUD, controles, domínio 16×16, grid 128×128, yaw, RippleField, motionGain, T007, cores, glow, bloom, partículas ou master.','',
 '## Metodologia e features','',
 'Os 12 WAVs T007 são verificados contra os hashes armazenados nos cues aprovados. FFmpeg faz apenas decodificação e resampling técnico para 16 kHz estéreo; nenhum WAV é regravado, amplificado ou normalizado. A identidade e os índices dos 10.282 cues existentes são preservados. A análise NÃO tenta gerar uma nova verdade de onset nem recuperar ataques filtrados na V1.2.','',
 '| Feature | Unidade/método | Função mensurável |','|---|---|---|',
 '| RMS/envelope | RMS estéreo de potência, janela centrada 64 ms, hop 20 ms; média 100 ms | energia absoluta, atividade e sustentação |',
 '| Peak local / crest factor | peak do sinal reamostrado; peak/RMS | distribuição robusta para futura V1.3B; não é true peak nem regra de altura |',
 '| Energia integrada | soma RMS² × hop; aproximação energética por janela | duração versus intensidade; pooled por fonte, não loudness do master |',
 '| Flux espectral | diferenças positivas de magnitude FFT, sem normalização por fonte | evidência de novidade e futura inspeção de ataques |',
 '| Centroide e flatness espectral | Hz; flatness de potência | hipótese de tom estável versus textura; não transcrição de pitch |',
 '| IOI / variância / CV / correlação | intervalos dos cues da MESMA fonte | regularidade, aceleração, desaceleração e densidade |',
 '| Tendência energética | correlação tempo × log-RMS, diferença em dB entre quintis | crescendo/decrescendo consistente, rejeitando flutuação pequena |',
 '| timeToRmsPeak / timeAfterRmsPeak | segundos dentro do gesto | localização mensurada do pico; não estimativa precisa de ADSR de uma nota |',
 '| sustainAboveActivityFloorSeconds | energia acima do piso após 150 ms | suporte temporal real, distinto do comprimento total do gesto |',
 '| T007 | ângulo unwrapped, elevação, distância e X/Z originais | trajetória com causa espacial conhecida durante energia ativa |','',
 'Zero crossings não foram acrescentados: não sustentam uma decisão adicional confiável neste material polifônico. A intensidade de cada gesto é RMS absoluto; attackStrength mantém o RMS original dos cues; sustainStrength é RMS posterior a 150 ms. Não há novo Dynamic Visual Headroom, teto de altura ou normalização relativa por stem.','',
 '## Taxonomia, regras e thresholds','',
 '| Tipo | Evidência exigida / limite |','|---|---|',
 '| IMPULSE | envelope retorna a 25% do pico local ou piso em 20–350 ms; referência ao ataque preservada |',
 '| REPEATED_PULSE / SEQUENCE | 2–3 / >=4 ataques; CV IOI <=0,18, janela <=8 s, gaps <=1,25 s; par exige IOI 0,12–1,25 s |',
 '| ACCELERATING / DECELERATING | >=4 ataques, correlação IOI × índice >=0,65 em módulo e razão entre terços >=1,3 |',
 '| TREMOLO_OR_ROLL | >=6 ataques, >=8 Hz, CV <=0,35; busca local <=2 s, gaps <=0,18 s e contraste RMS mediano dentro dos IOIs >=15% |',
 '| SUSTAINED_TONE / TEXTURE | energia contínua >=0,6 s; furos internos <=120 ms; cortes explícitos a cada 8 s; tom: flatness <0,08 e CV centroide <0,35 |',
 '| CRESCENDO / DECRESCENDO | janela >=2 s, suporte ativo >=90%, variação >=6 dB e correlação absoluta >=0,8; união somente se a regra continuar válida |',
 '| PHRASE | agrupamento temporal da MESMA fonte; gap >1,4 s delimita; limite operacional 12 s |',
 '| CONTINUOUS_MOTION | energia sustentada + variação T007 >=10° azimute ou >=5° elevação ou >=0,15 m distância |',
 '| TRANSITION | não inferido: não há modelo validado de mudança de seção/harmonia; não inventar exemplos |','',
 'O piso de atividade é max(1e-6, 0,06×P95 do envelope por fonte). É somente um critério reversível de segmentação: os valores de áudio/energia/intensidade permanecem absolutos, e o piso usado é registrado em cada estatística. Não aumenta stems fracos. Para ruído, caudas HRTF e fontes muito baixas, o piso pode influenciar a divisão de regiões e precisa de revisão.','',
 '## Hierarquia e identidade','',
 'Os ataques são referências estáveis `index` para o dataset V1.2 e mantêm source/time/amplitude/strength originais. Relações `containsAttack` ligam gestos a ataques; `containsGesture` liga uma PHRASE a gestos totalmente contidos da mesma fonte. Toda referência de ataque pertence à mesma fonte do gesto, sem mistura entre Drums/Percussion/Bass/vozes. Todos os 10.282 ataques pertencem a ao menos uma frase temporal. Não existe ciclo: frases são os únicos pais de gestos e não são filhas de outras frases.','',
 'As camadas podem se sobrepor: uma frase pode conter uma sequência, energia sustentada e uma tendência. Isso não significa movimentos simultâneos futuros. Deduplicação semântica, arbitragem de saliência e interação entre fontes NÃO são executadas nesta fase. Nenhuma análise desta fase exige escolher entre um grupo e seus ataques constituintes.','',
 '## Confidence e ambiguidades','',
 'Confidence é um score heurístico de suporte da regra, não probabilidade calibrada: impulso 0,80; sustain espectral 0,72; frase temporal 0,60; movimento conhecido T007 0,95; repetição/tendência variam conforme regularidade/correlação, com tetos 0,85–0,95. Os valores não foram validados contra anotação humana. Alto score de periodicidade prova regularidade do detector, não garante interpretação musical de compasso ou técnica.','',
 'Tom sustentado pode ser harmônico/polifônico ou ressonância de percussão; textura não significa instrumento específico. Tremolo/roll é candidato de ataques densos e regulares, sem certeza de técnica instrumental. Crescendos podem refletir execução, automação e processamento espacial do stem; não se atribui intenção expressiva apenas pela curva. PHRASE é proxy de gaps e cortes operacionais, não teoria musical completa. Os cortes de 8/12 s são artefatos declarados de segmentação.','',
 'A inspeção gráfica inicial identificou uma sequência densa de Bass com envelope relativamente contínuo. O detector foi corrigido para não tratar timestamps próximos como prova suficiente de roll: agora exige contraste RMS mediano >=15% dentro dos intervalos. Sequências densas sem modulação suficiente ficam somente como REPEATED_PULSE_SEQUENCE com confidence 0,55 e limitação explícita. O teste de tom contínuo com cues densos rejeita roll. Mesmo com modulação, roll/tremolo continua hipótese de estrutura, não técnica instrumental comprovada.','',
 'Uma faixa fraca pode apresentar sustain sem cue inicial: isso é permitido e documentado, com attackRefs vazio. Não se inventa ataque para completar um gesto. A separação dos stems e a automação T007 são fontes de verdade de identidade/posição, não reconstrução binaural a partir de stereo. A lei de legibilidade não pode ser provada por esta camada analítica; será uma restrição obrigatória do futuro behavior engine.','',
 '## Resultados por stem','',
 '| Stem | Ataques preservados | Gestos | Duração média s | RMS P50 / P95 / MAX | Confidence média |','|---|---:|---:|---:|---|---:|']
 for s in d['stemStatistics']:
  p=s['rmsDistribution'];lines.append(f'| {s["source"]} | {s["attackCount"]} | {s["gestureCount"]} | {s["meanDuration"]:.3f} | {p["P50"]:.6f} / {p["P95"]:.6f} / {p["MAX"]:.6f} | {s["meanConfidence"]:.3f} |')
 lines+=['',f'Total: **{len(d["gestures"])} gestos**, **{len(d["relationships"])} relações**, 12 fontes e 10.282 ataques preservados. P50/P75/P90/P95/P99/MAX de RMS, peak e intensidade de gesto estão em `analysis-summary.json`, por fonte e globalmente. As distribuições globais agrupam observações por fonte; não representam soma acústica ou LUFS do master.','', '| Tipo | Quantidade |','|---|---:|']
 for kind,item in d['taxonomy'].items():lines.append(f'| {kind} | {item["count"]} |')
 lines+=['', 'Distribuição por tipo e stem:','']
 for s in d['stemStatistics']:lines.append(f'- **{s["source"]}:** '+', '.join(f'{k}={n}' for k,n in s['types'].items()))
 lines+=['', '## Exemplos reais selecionados automaticamente','', '| Tipo | Stem | Início–fim s | Confidence | RMS absoluto | Ataques |','|---|---|---|---:|---:|']
 for g in cases:
  if g['found']:lines.append(f'| {g["gestureType"]} | {g["source"]} | {g["startTime"]:.3f}–{g["endTime"]:.3f} | {g["confidence"]:.3f} | {g["intensity"]:.6f} | {len(g["attackRefs"])} |')
  else:lines.append(f'| {g["gestureType"]} | não encontrado com suporte >=0,72 | — | — | — | — |')
 lines+=['','`cases.json` contém as features, índices de ataques, evidências e trajetórias completas de cada exemplo. A seleção usa maior confidence, desempate por intensidade RMS absoluta, número de ataques, tempo e fonte; nenhum exemplo é inventado.','',
 '## Espaço, determinismo e sanity','',
 f'{sanity["trajectorySamplesChecked"]} amostras espaciais conferidas contra o interpolador T007 original, tolerância 2e-5, erro máximo observado {sanity["maximumSpatialError"]:.9g}. Cada gesto inclui início/pico/fim e amostras a cada 250 ms, mais os knots de automação internos. Azimute permanece unwrapped; repetir um tempo de automação mantém a última chave, conforme o mapping aprovado. Elevação, distância e X/Z são preservados numericamente, sem novo mapeamento para a malha.','',
 f'Duas análises completas independentes dos 12 WAVs geraram JSON **byte-idêntico**, SHA-256 `{det["sha256Run1"]}`. As 12 séries de features também são byte-idênticas. Não há seed aleatória, timestamp de geração ou caminho absoluto de máquina no artefato. Ambiente/versões são registrados; determinismo entre versões diferentes de FFmpeg/NumPy não é alegado.','',
 'Sanity PASS: schema, fontes válidas, IDs únicos, start<=peak<=end, duração, ordenação, finitude recursiva, confidence [0,1], referências ínteg ras e espaço dentro dos limites. Artefato complementar criado sem substituir cues.','',
 '## Regressão V1.2 e testes','',
 f'- 82 testes anteriores PASS; {checks["newTests"]} novos testes PASS; **{checks["totalTests"]} testes no total**.',
 '- Novos testes cobrem DSP determinístico, RMS estéreo antifase, relações absolutas de intensidade, schema, ordem, fontes, hierarquia, repetição, aceleração/desaceleração, roll local, sustentação/impulso, tendências e rejeição de pequenas flutuações, confidence, interpolação espacial, source hashes e referências.',
 '- Playback real integral 330 s: **10.282/10.282**, 10.282 únicos, zero dropped/duplicate/unexpected reset; sem erro de console/mídia.',
 '- Capturas 0 / 46,5 / 200,5 s: PNGs byte-idênticos à baseline V1.2, portanto pixel-idênticos.',
 '- Build produção PASS; permanece o aviso histórico de bundle >500 kB. git diff --check PASS.',
 '- Nenhum teste anterior foi removido ou alterado. Nenhum código de produção foi alterado.','',
 '## Evidências e reprodução','',
 '- Artefato: `visualizer/public/audio/tukana-musical-gestures-v1.json`.',
 '- Índice visual: `visualizer/reports/v1_3a-musical-gesture-intelligence/index.html`.',
 '- Visão 330 s: `timelines/overview-0-330.svg`; 11 zooms: `timelines/zoom-000-030.svg` até `zoom-300-330.svg`.',
 '- Gráficos dos casos encontrados: `timelines/case-*.svg`; dados completos: `cases.json`; espaço T007 por stem: `timelines/spatial-trajectories.svg`.',
 '- Features temporais absolutas por stem: `features/*.json` (20 ms).',
 '- `determinism.json`, `sanity-checks.json`, `final-checks.json`, `pixel-regression.json`, `real-run-v13a.json` e logs preservam as verificações.',
 '- Scripts em `visualizer/tools`: `build_musical_gestures.py`, `musical_gestures.py`, `render_musical_gestures.py`, `validate_musical_gestures.py`, `validate_gesture_v12_regression.py`.',
 '', '```powershell','cd visualizer','python -B tools/build_musical_gestures.py','python -B tools/render_musical_gestures.py','python -B tools/validate_musical_gestures.py','node --test tests/*.test.js','python -B -m unittest discover -s tests -p "test_*.py"','npm run build','```','',
 '## Hashes de proveniência','', '| Entrada/analisador | SHA-256 |','|---|---|']
 for key,digest in d['sourceHashes'].items():lines.append(f'| {key} | `{digest}` |')
 for source,item in d['sources'].items():lines.append(f'| stem {source} | `{item["sha256"]}` |')
 lines+=['', '**Conclusão:** fundação analítica concluída, com classificação heurística revisável e rastreável. Aguardar revisão humana dos gráficos e dos casos. Não iniciar V1.3B, headroom, saliência ou comportamentos visuais nesta fase.','']
 (V/'reports/LAISE_VISUALIZER_V1_3A_MUSICAL_GESTURE_INTELLIGENCE.md').write_text('\n'.join(lines).replace('ínteg ras','íntegras'),encoding='utf-8')
 print('Report PASS written')
if __name__=='__main__':main()
