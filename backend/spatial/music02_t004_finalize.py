"""Keep T004 final trace metadata consistent with corrected home-referenced gain."""
import copy
from music02_t004 import OUT,load,dump

def run():
    r=load(OUT/'reports/M02_T004_validation.json')
    for role,details in r['source_reports'].items():
        assert 'pre_correction_trace' not in details
        details['pre_correction_trace']=copy.deepcopy(details['trace'])
        evidence=r['gain_reference_correction']['roles'][role]
        for tr in details['trace']:
            tr['growth_reference_distance_m']=evidence['home_distance_m']
            tr['retained_growth_db']=min(max(0,evidence['home_compensation_db']-tr['compensation_db']),2.5)
    dump(OUT/'reports/M02_T004_validation.json',r);print('Final T004 traces consistent')

if __name__=='__main__':run()
