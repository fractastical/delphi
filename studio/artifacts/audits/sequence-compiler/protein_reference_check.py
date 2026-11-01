"""Reference CDS identity checks only; no structure inference or functional claim."""
from pathlib import Path
from io import StringIO
from hashlib import sha256
import argparse
import json
from Bio import SeqIO


def check(root):
    raw_root = root / 'artifacts/sequence-evidence/raw'
    out = []
    for gene, rna in [('fgf20a', 'NM_001037103.2'), ('kcnh2a', 'NM_001042722.2')]:
        path = raw_root / f'{gene}-{rna}.gb'
        transcript = SeqIO.read(StringIO(path.read_text()), 'genbank')
        assert transcript.id == rna
        cds = [x for x in transcript.features if x.type == 'CDS']
        assert len(cds) == 1
        protein_id = cds[0].qualifiers['protein_id']
        rows, translated = [], []
        for path in [raw_root / f'{gene}-genomic.gb', path]:
            data = path.read_bytes()
            record = SeqIO.read(StringIO(data.decode()), 'genbank')
            features = [x for x in record.features if x.type == 'CDS' and x.qualifiers.get('protein_id') == protein_id]
            assert len(features) == 1
            feature = features[0]
            dna = feature.extract(record.seq)
            peptide = str(dna.translate(to_stop=True))
            annotated = feature.qualifiers['translation'][0]
            translated.append(peptide)
            rows.append({'path': str(path.relative_to(root)), 'sha256': sha256(data).hexdigest(),
                         'protein_id': protein_id[0], 'CDS_nt': len(dna), 'translated_aa': len(peptide),
                         'translated_sha256': sha256(peptide.encode()).hexdigest(),
                         'annotated_sha256': sha256(annotated.encode()).hexdigest(),
                         'translation_equals_annotation': peptide == annotated,
                         'source_notes': feature.qualifiers.get('note', [])})
        assert len(translated[0]) == len(translated[1])
        differences = [{'position_1based': i+1, 'genomic_CDS_aa': a, 'RefSeq_CDS_aa': b}
                       for i, (a, b) in enumerate(zip(*translated)) if a != b]
        out.append({'gene': gene, 'records': rows, 'protein_differences': differences,
                    'protein_difference_count': len(differences)})
    return {'schema': 'frontier.reference-CDS-identity/1', 'genes': out, 'new_inference': False,
            'scope': 'Exact source annotation and standard CDS translation only; no protein structure, conductance, experimental allele or functional validation',
            'queue_decision': 'No new inference justified by these reference differences alone; independent variant-specific functional observable missing'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = check(args.root.resolve())
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({row['gene']: row['protein_difference_count'] for row in result['genes']}))
