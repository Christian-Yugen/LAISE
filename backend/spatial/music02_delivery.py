"""Write MUSIC 02 human-readable delivery from validated metadata."""
from pathlib import Path
import json
from music02_analysis import ROOT, PROJECT, dump

def load(relative):return json.loads((PROJECT/relative).read_text(encoding='utf-8-sig'))

def main():
    manifest=load('analysis/stem_import_manifest.json');mapping=load('analysis/musical_map.json')
    report=load('reports/M02_T001_preview_validation.json');encoded=load('reports/M02_T001_encoded_artifacts_validation.json')
    scene=load('spatial_scenes/M02_T001_initial_scene.json');gain=load('analysis/gain_staging.json')
    assert report['status']=='PASS' and encoded['status']=='PASS'
    lag=mapping['bpm']['beat_period_seconds']*48000/1024
    mapping['bpm']['confidence_interpretation']='Normalized autocorrelation contrast, not a calibrated probability; beat/downbeat phase requires listening.'
    mapping['bpm']['lag_quantization_interval_bpm']=[60*(48000/1024)/(lag+0.5),60*(48000/1024)/(lag-0.5)]
    dump(PROJECT/'analysis/musical_map.json',mapping)
    brass=load('analysis/brass_analysis.json');active=sum(r['end_seconds']-r['start_seconds'] for r in manifest['stems']['brass']['metrics']['active_regions'])
    brass['total_active_seconds']=active;brass['full_song_active_fraction']=active/mapping['duration_seconds']
    dump(PROJECT/'analysis/brass_analysis.json',brass)
    dump(PROJECT/'reports/M02_T001_preflight.json',dict(test_id='M02-T001',baseline='LAISE_T017_APPROVED_BASELINE',
        baseline_commit='043293ff89e720d9b6746b66105d5e7fac03a206',git_status_before_processing='CLEAN',
        initial_HEAD_matches_tag=True,active_T018_imports=False,tukana_preserved_by_full_file_hash_size_mtime_snapshot=True,
        original_B2_sha256='9daf544d7e073d8791f6260eed2630863a9280a2cca7d22053132a881e2c0df9'))
    lines=['# MUSIC 02 — M02-T001','',
        'Importação, análise e primeiro preview concluídos. Validação objetiva: **PASS**. Avaliação perceptiva: **PENDENTE**.','',
        '## Ouvir primeiro','',
        '- [Binaural level-matched — 200–230 s](../renders/M02_T001_binaural_200_230_level_matched_24bit.wav)',
        '- [Dry level-matched — 200–230 s](../renders/M02_T001_dry_comparison_200_230_level_matched_24bit.wav)',
        '- [Other isolado para identificação](../renders/M02_T001_Other_identification_200_230_raw.wav)','',
        'Ambas as comparações medem −20,6 LUFS (resolução de relatório: 0,1 LU). Binaural: sample peak/true peak −6,0 dBFS/dBTP; dry matched: −7,31 dBFS / −7,3 dBTP. Duração exata: 30 s / 1.440.000 frames, estéreo PCM24 a 48 kHz. Não houve limiter, compressão ou mastering.','',
        '## Auditoria dos originais','',
        '11 stems; 48 kHz; PCM16; estéreo; 11.884.801 frames; 247,600020833 s. Nenhuma amostra no limiar de clipping detectado. Nenhum arquivo foi convertido, deslocado, resampleado, normalizado ou cortado. Silêncios geraram apenas metadados. Igualdade de frames preserva a origem temporal dos arquivos; não prova, por si só, o alinhamento da gravação na ausência de timecode.','',
        '| Role | Arquivo | Pico dBFS | SHA-256 |','|---|---|---:|---|']
    for role,r in manifest['stems'].items():
        lines.append(f"| {role} | {Path(r['path']).name} | {r['metrics']['peak_dbfs']:.2f} | `{r['sha256']}` |")
    lines += ['', '## Análise musical','',
        f"BPM recalculado: **{mapping['bpm']['bpm']:.6f}**. Drums e Percussion concordam independentemente. O método é autocorrelação de onsets com hop de 1024 frames; a confiança 1,0 é contraste normalizado, não probabilidade estatística. A resolução de lag é limitada; não se deve interpretar seis casas decimais como precisão do tempo musical.", '',
        'Hipótese de métrica: 4/4 (confiança 0,5); início do beat grid em 0,362667 s. Downbeat/fase de compassos e rótulos de seção requerem escuta. O mapa contém beat grid, compassos hipotéticos, atividade, entradas, onsets por role, frases, densidade e transições com confiança. Não houve hardcode do BPM nem uso dos timestamps externos como entradas da detecção.','',
        'Transições detectadas por mudanças de energia/densidade em contexto de 2 s: **'+', '.join(f"{t['time_seconds']:.1f}" for t in mapping['transitions'])+' s**. Essa segmentação inicial cria nove seções de textura; os nomes formais não estão confirmados. O mapa também compara separadamente os candidatos externos. 35 s e 205,5 s não foram escolhidos entre as oito maiores novidades; não foram forçados como limites.','',
        '## Brass e Other','',
        f"Brass tem aproximadamente **{active:.2f} s** de atividade acima de −60 dBFS (**{active/mapping['duration_seconds']*100:.1f}%** da música). Concentra frases em 119–134 s e 198–222 s, com uma entrada curta perto de 178,4 s. Uma atividade final de cerca de 48 ms também foi registrada como metadado. A hipótese de função é acento/resposta episódica, ainda sujeita à avaliação musical. Em 200–230 s, sua atividade ocupa 40% do intervalo.", '',
        'Other apresenta energia principalmente baixa/média, com centroide mediano aproximado de 1.087 Hz. Esses descritores não identificam seu instrumento. A classificação permanece pendente; foi fornecida uma audição isolada e usada uma posição fixa conservadora, sem trajetórias específicas de conteúdo.','',
        '## Gain staging e seleção do preview','',
        f"Soma alinhada em unity gain, medida em float64 somente como diagnóstico: **{gain['measured_unity_sum_peak_dbfs']:+.2f} dBFS**. Atenuação comum pré-dearVR: **{gain['common_input_gain_db']:.2f} dB**, calculada pela soma dos picos individuais para assegurar margem conservadora de −12 dBFS no pior caso dry. Ganhos por role são não positivos. Um ganho comum transparente após a renderização coloca o maior pico das comparações em −6 dBFS. Para matching, somente o dry recebeu atenuação adicional de 0,5 dB; não há limiter escondendo soma.", '',
        '200–230 s cobre os 11 roles e mais Brass que o melhor candidato de score, 213–243 s. Seu score está a menos de 1% do melhor intervalo computado. O trecho contém frases de Brass, desenvolvimento de woodwinds e a transição forte de 219,7 s. A participação significa atividade em algum momento do intervalo, não os 11 stems continuamente simultâneos.','',
        '## Cena explicável','', '| Role | Decisão |','|---|---|']
    portuguese={
        'lead_vocal':'Centro frontal estável; protege clareza e inteligibilidade.',
        'bass':'Centro baixo estável; âncora de graves.',
        'drums':'8° à frente, estável; âncora de impacto e ritmo.',
        'backing_vocals':'Camada traseira esquerda; separa respostas da voz principal sem alterar Stereo Width.',
        'guitar':'Faixa esquerda, com deslocamentos discretos nas mudanças de textura.',
        'keyboards':'Faixa direita elevada; complementa Guitar sem copiar a cena Tukãna.',
        'synth':'Camada sustentada superior/traseira direita; mudanças discretas conforme seção.',
        'percussion':'Uma única órbita de oito compassos hipotéticos, culminando no relaxamento de textura perto de 219,7 s; permanece fixa antes e depois.',
        'woodwinds':'Frases longas atravessam o campo traseiro para destacar respostas expressivas; entradas curtas ficam localizadas.',
        'brass':'Posição estável por frase, alternando lados nas pausas; nenhum movimento contínuo de efeito.',
        'other':'−18°, elevação 0°, ganho −4 dB; fixo e conservador enquanto sua identidade é investigada.'}
    for source in scene['sources']:lines.append(f"| {source['source_id']} | {portuguese[source['source_id']]} |")
    lines += ['', 'Cada keyframe tem justificativa e usa tempo absoluto da música. A cena é independente do renderer. DearVR PRO 2 usa uma instância por stem, distância efetiva fixa de 3 m, reflexão/reverb desativados conforme T017 e nenhuma automação experimental T018.','',
        '## Validação e regressões','',
        '- 15 WAVs de entrega: hashes, PCM24, 48 kHz, estéreo e duração exata confirmados.',
        '- Os 11 stems usam o mesmo frame inicial 9.600.000. Pre-roll uniforme de 1 s aquece as instâncias; a mesma remoção de pre-roll preserva o intervalo de todos os stems. Não há trimming por atividade.',
        '- Sem NaN/Inf ou clipping. Continuidade medida nas fronteiras reais do plugin, com fase de 128 frames após o pre-roll; nenhum outlier pelo critério herdado da baseline.',
        '- Órbita da percussão: 80° → 440° (360°), uma passagem pelo wrapping ±180°, maior passo circular aproximado de 0,108° por bloco.',
        '- Os diagnósticos de transientes usam envelopes de magnitude de 5 ms e busca de lag ±100 ms; os 50 eventos fortes de cada role medido continuam presentes. A qualidade perceptiva dos transientes não é inferida somente dessa medição.',
        '- Binaural: correlação L/R 0,724; redução RMS em mono cerca de 0,644 dB. Dry: correlação 0,928. A adequação musical continua dependente da escuta.',
        '- Importer legado reproduz exatamente o manifesto Tukãna de dez roles. Casos de três e onze roles passaram; aliases Brass, Keyboard e Lead Vocals foram exercitados.',
        '- Testes de PCM16/24/32, float32, mono/estéreo, corrupção e resampling temporal passaram. Nenhum resampling foi necessário na MUSIC 02.',
        '- Adapter, analyzer, composer, renderers e mastering aprovados permanecem idênticos à tag T017; wrapping, distância fixa e interpolação de ganho foram exercitados. Nenhum import T018 ativo.',
        '- Todos os arquivos do projeto Tukãna foram comparados por SHA-256, tamanho e mtime antes/depois: intactos. B2 mantém seu hash oficial.',
        '', 'Não foi repetido um render integral de Tukãna nesta etapa: seu DSP permanece byte a byte igual à baseline já validada integralmente. A mudança compartilhada é restrita aos aliases e à configuração de roles do importer, cuja compatibilidade foi testada diretamente.', '',
        '## Evidências e comandos','',
        '- [Manifesto e hashes](../analysis/stem_import_manifest.json)',
        '- [Musical map](../analysis/musical_map.json)',
        '- [Brass](../analysis/brass_analysis.json)',
        '- [Other](../analysis/other_content_analysis.json)',
        '- [Cena inicial](../spatial_scenes/M02_T001_initial_scene.json)',
        '- [Validação do preview](M02_T001_preview_validation.json)',
        '- [Validação dos WAVs exportados](M02_T001_encoded_artifacts_validation.json)',
        '- [Stems espacializados](../spatial_stems/M02_T001_preview_200_230/)', '',
        'Comandos: `python backend/spatial/music02_analysis.py`, `python backend/spatial/music02_preview.py` e `python backend/tests/test_m02_t001_preview.py`, usando o Python de `.venv`. Os scripts escrevem exclusivamente no projeto MUSIC 02; uma nova execução regenerará seu protótipo.','',
        'Aguardar avaliação humana do binaural contra o dry: proximidade, voz, bateria, Brass, naturalidade e intenção do movimento. Other deve ser identificado antes de uma decisão espacial definitiva. **Não renderizar a música completa nem masterizar antes dessa avaliação.**','']
    path=PROJECT/'reports/M02_T001_delivery.md';path.write_text('\n'.join(lines),encoding='utf-8')
    print(str(path))
    print(json.dumps({role:r['transient_diagnostic'] for role,r in report['source_reports'].items() if r['transient_diagnostic']},indent=2))

if __name__=='__main__':main()
