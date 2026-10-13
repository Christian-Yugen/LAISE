"""Produce the T003 listening index and technical report from measured results."""
from pathlib import Path
from music02_t003 import OUT,load

def link(entry,label):
    return f"- [{label}]({Path(entry['path']).relative_to(OUT).as_posix()})"

def main():
    r=load(OUT/'reports/M02_T003_validation.json');test=load(OUT/'reports/M02_T003_encoded_regression.json')
    scene=load(OUT/'spatial_scenes/M02_T003_scene.json');assert r['objective_status']=='PASS' and test['status']=='PASS'
    lines=['# M02-T003 — Spatial Separation & Near-Field 360','',
        'Preview e monitores concluídos. Critérios técnicos: **PASS**. Separação tridimensional e preferência perceptiva: **PENDENTES**.','',
        '## Comparação — 200–230 s','']
    for key,title in [('T001_reference','T001 preservada — referência'),('T002_reference','T002 preservada — referência'),('T003_near_field','T003 — separação angular e near-field')]:
        lines.append(link(r['comparison'][key]['level_matched'],title))
    lines += ['', '| Comparação | LUFS integrados | True peak dBTP | Correlação L/R |','|---|---:|---:|---:|']
    for label,entry in r['comparison'].items():
        m=entry['level_matched'];lines.append(f"| {label} | {m['loudness']['integrated_lufs']:.1f} | {m['loudness']['true_peak_dbtp']:.1f} | {m['signal']['lr_correlation']:.3f} |")
    lines += ['', 'Todas as versões musicais têm 30 s / 1.440.000 frames, estéreo PCM24 a 48 kHz. As cópias de referência recebem somente ganho vinculado para matching; os arquivos T001/T002 originais permanecem intactos. Não houve limiter, mastering ou render completo.','',
        '## Avaliar posições, não nomes de instrumentos','',
        link(r['simplified_monitor']['same_sound_sequence'],'Monitor simplificado — mesmo som, oito direções e três alturas (27,5 s)'),
        link(r['simplified_monitor']['four_source_mix'],'Monitor simplificado — quatro fontes simultâneas (200–215 s)'),
        link(r['percussion_sector_monitor'],'Percussion isolada — oito setores e volta completa (200–230 s)'), '',
        'O primeiro monitor usa exatamente o mesmo trecho composto de Percussion, Woodwinds e Backing em todas as direções, sempre a 1 m. O composto é dual-mono apenas para esse diagnóstico, evita soma de canais em oposição de fase e recebe matching de nível. Assim, mudanças de instrumento ou distância não dão a resposta. Há 2 s de som e 0,5 s de pausa por posição.','',
        'A montagem diagnóstica tem organização temporal própria e fades de 20 ms nas bordas; nenhum original foi cortado ou alterado. O preview musical mantém os tempos absolutos. O monitor simultâneo preserva 200–215 s, usa quatro fontes a 1 m e menor densidade que a música.','',
        'Na primeira escuta, registre direção, altura e clareza antes de consultar a sequência esperada abaixo. Reconhecer o instrumento não faz parte do teste.','',
        '| Cue | Tempo no monitor | Direção esperada |','|---|---|---|']
    names={'front-right':'frente-direita','right':'direita','rear-right':'trás-direita','rear':'trás','rear-left':'trás-esquerda','left':'esquerda','front-left':'frente-esquerda','front':'frente','front-low':'frente-baixo','front-level':'frente-altura normal','front-high':'frente-alto'}
    for cue in r['simplified_monitor']['schedule']:
        lines.append(f"| {cue['cue']} | {cue['start_seconds']:.1f}–{cue['end_seconds']:.1f} s | {names[cue['expected_direction']]} |")
    lines += ['', 'Monitor simultâneo: A frente-direita (45°/0°), B frente-esquerda (−45°/15°), C trás-esquerda (−135°/0°), D trás-direita elevada (135°/35°). Compare se percebe quatro posições/camadas, sem exigir quatro nomes.','',
        '## Cena próxima e separação','', '| Fonte | Posição de referência | Distância de referência | Intenção |','|---|---|---:|---|']
    for s in scene['sources']:
        k=s['keyframes'][0];d=s['distance_keyframes'][0]['distance_m']
        reasons={'lead_vocal':'Âncora frontal, compactação candidata.', 'bass':'Âncora central baixa, separada da voz pela elevação.',
            'drums':'Âncora frontal baixa, deslocamento angular moderado.', 'guitar':'Faixa frontal esquerda.', 'keyboards':'Faixa frontal direita elevada.',
            'backing_vocals':'Lateral/traseira próxima, envolve sem tomar o centro.', 'percussion':'Órbita com oito setores; raio quase constante.',
            'woodwinds':'Travessias lateral/frontal expressivas, sem órbita completa.', 'synth':'Camada traseira direita alta.',
            'brass':'Entradas pontuais em lados traseiros baixos.', 'other':'Posição fixa, ganho conservador; identidade pendente.'}
        lines.append(f"| {s['source_id']} | {k['azimuth_deg_unwrapped']:g}° / {k['elevation_deg']:g}° | {d:g} m | {reasons[s['source_id']]} |")
    lines += ['',
        'A maior parte da cena usa 0,85–1,6 m; Woodwinds tem aproximação pontual a 0,5 m e Backing a 0,6 m. Nenhuma fonte do preview vai além de 1,8 m. Azimute, frente/trás, elevação e trajetória são as pistas principais; a variação de raio é secundária.','',
        'Lead/Bass compartilham azimute central por função de âncora, mas diferem 42° em elevação. Drums permanece estável em 18°/−20°. Guitar e Keyboard ficam em lados frontais opostos. Other recebe faixa estática traseira esquerda e mantém ganho −4 dB; não se inferiu sua identidade nem se acrescentou movimento.','',
        'Lead e Percussion usam redução de Side a 50% antes do dearVR, com restauração RMS vinculada, como candidatos T003. Os demais stems mantêm imagem estéreo original. Não se adotou mono na música nem se alterou Stereo Width, Clarity, HRTF, reflection, reverb ou occlusion do plugin.','',
        'O controle de ganho por distância reutiliza a calibração medida na T002 e controla separadamente a loudness média de cada stem contra sua referência T001. A curva transferida é aproximada; o matching final limita confusão de volume médio. Loudness instantânea não é garantida idêntica.','',
        '## Órbita e movimento expressivo','',
        'Percussion inicia frente-direita em 45°, visita os oito setores e retorna em 405°, completando 360°. Cada setor tem pausa de 0,45 s, seguida de interpolação contínua. Raio 0,9 m e elevação −15° ficam constantes; profundidade não serve como pista para nomear o setor. O ciclo cobre aproximadamente 200,043–217,792 s.','',
        '| Setor | Tempo absoluto de chegada | Azimute desembrulhado |','|---|---:|---:|']
    for e in r['sector_events']:lines.append(f"| {names[e['sector']]} | {e['start_seconds']:.3f} s | {e['azimuth_unwrapped_deg']}° |")
    lines += ['',
        'Woodwinds percorre −75° → frente elevada → +75° na primeira frase (200–207,019 s), e a trajetória inversa na segunda (218,709–224,427 s). Assim, seu gesto frontal/lateral difere da órbita de Percussion. O ponto próximo ocorre na primeira frase; a elevação frontal distingue a passagem do centro vocal. Brass muda de lado nas pausas e fica parado durante os acentos.','',
        '## Validação e limites','',
        f"- {test['verified_pcm24_wavs']} WAVs verificados por hash, PCM24, 48 kHz, estéreo e frames exatos.",
        '- Onze instâncias dearVR independentes, mesma janela 200–230 s, pre-roll comum de 1 s e mesma remoção de pre-roll; sem trimming por atividade.',
        '- Sem NaN/Inf, clipping ou true peak inseguro. Continuidade de blocos e wrapping ±180° passaram nos critérios técnicos.',
        '- Lead, Bass e Drums possuem poses constantes. Percussion tem 360° completos e oito eventos distintos; Woodwinds não faz uma órbita completa.',
        '- Todos os arquivos anteriores MUSIC 02, incluindo T001/T002, e todos os arquivos Tukãna: SHA-256, tamanho e mtime preservados.',
        '- Regressões da baseline T017 passaram; adapter, composer e pipelines aprovados permanecem intocados. Nenhum import de T018.', '',
        'A auditoria de separação mede ângulos geométricos entre fontes ativas. Trajetórias contínuas cruzam temporariamente algumas faixas ocupadas; esses cruzamentos estão registrados, não escondidos. Distância angular nominal não equivale a direção percebida, e uma coordenada traseira pode continuar sendo ouvida como frontal conforme HRTF/ouvinte. O display de distância do plugin arredonda a 0,1 m.','',
        'O sucesso perceptivo depende de ouvir múltiplas fontes distintas, direções diferentes, frente/trás, altura, passagem ao redor da cabeça, proximidade, clareza e pouca confusão espacial. Um arquivo tecnicamente correto não prova esses resultados.','',
        '## Avaliação humana','',
        'Para cada comparação, registrar: número aproximado de posições distinguíveis; diferença frente/trás; altura; continuidade da volta; proximidade física; clareza; confusão; conforto. Depois indicar preferência T001/T002/T003. Nos monitores, registrar direções percebidas e quantidade de fontes, sem exigir identificação de instrumentos.','',
        '- [Cena independente do renderer](spatial_scenes/M02_T003_scene.json)',
        '- [Relatório técnico, métricas e controles](reports/M02_T003_validation.json)',
        '- [Auditoria angular entre fontes ativas](reports/angular_separation.json)',
        '- [Cronograma e método dos monitores](reports/simplified_monitor.json)',
        '- [Regressão dos arquivos exportados](reports/M02_T003_encoded_regression.json)', '',
        '**Aguardar avaliação humana antes de prosseguir. Nenhum render completo ou mastering foi realizado.**','']
    path=OUT/'README.md';assert not path.exists();path.write_text('\n'.join(lines),encoding='utf-8');print(path)

if __name__=='__main__':main()
