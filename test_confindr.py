import shutil
import os
from new_confindr import *
from Bio import SeqIO


def test_present_dependency():
    assert dependency_check('ls') is True


def test_nonexistent_dependency():
    assert dependency_check('fake_dependency') is False


def test_r1_fastqs():
    assert find_paired_reads('tests/fake_fastqs/') == [['tests/fake_fastqs/test_R1.fastq.gz',
                                                        'tests/fake_fastqs/test_R2.fastq.gz']]


def test_1_fastqs():
    assert find_paired_reads('tests/fake_fastqs/', forward_id='_1',
                             reverse_id='_2') == [['tests/fake_fastqs/test_1.fastq.gz',
                                                   'tests/fake_fastqs/test_2.fastq.gz']]


def test_empty_fastqs():
    assert find_paired_reads('tests/fake_fastqs/', forward_id='_asdf', reverse_id='_fdsa') == []


def test_mashsippr_run():
    assert run_mashsippr('tests/mashsippr', 'tests/mashsippr/mashsippr_results', 'databases') is True
    shutil.rmtree('tests/mashsippr/O157')
    shutil.rmtree('tests/mashsippr/mashsippr_results')


def test_mashsippr_read():
    assert read_mashsippr_output('tests/mash.csv', 'O157') == 'Escherichia'


def test_mashsippr_read_fail():
    assert read_mashsippr_output('tests/mash.csv', 'NotInTheFile') == 'NA'


def test_genus_exclusion_positive():
    assert find_genusspecific_alleles('databases/profiles.txt', 'Escherichia') == ['BACT000060', 'BACT000065']


def test_genus_exclusion_negative():
    assert find_genusspecific_alleles('databases/profiles.txt', 'NotARealGenus') == []


def test_rmlst_bait():
    pair = ['tests/mashsippr/O157_R1.fastq.gz', 'tests/mashsippr/O157_R2.fastq.gz']
    actual_result = 'AAAAAAACAGCAAATCCGGTGGTCGTAACAACAATGGCCGTATCACCACTCGTCATATCGGTGGTGGCCA' \
                    'CAAGCAGGCTTACCGTATTGTTGACTTCAAACGCAACAAAGACGGTATCCCGGCAGTTGTTGAACGTCTT' \
                    'GAGTACGATCCGAACCGTTCCGCGAACATCGCGCTGGTTCTGTACAAAGACGGTGAACGCCGTTACATCC' \
                    'TGGCCCCTAAAGGCCTGAAAGCTGGCGACCAGATTCAGTC'
    extract_rmlst_genes(pair, 'databases/rMLST_combined.fasta', 'tests/asdf_R1.fasta', 'tests/asdf_R2.fasta')
    thing = SeqIO.read('tests/asdf_R1.fasta', 'fasta')
    assert str(thing.seq) == actual_result
    os.remove('tests/asdf_R1.fasta')
    os.remove('tests/asdf_R2.fasta')
