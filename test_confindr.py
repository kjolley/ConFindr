import shutil
import os
from confindr.confindr import *
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


# def test_mashsippr_run():
#    assert run_mashsippr('tests/mashsippr', 'tests/mashsippr/mashsippr_results', 'databases') is True
#    shutil.rmtree('tests/mashsippr/O157')
#    shutil.rmtree('tests/mashsippr/mashsippr_results')


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


def test_read_subsampling():
    subsample_reads('tests/mashsippr/O157_R1.fastq.gz', 'tests/mashsippr/O157_R2.fastq.gz', 2, 1000, 'tests/asdf_R1.fasta', 'tests/asdf_R2.fasta')
    thing = SeqIO.parse('tests/asdf_R1.fasta', 'fasta')
    bases = 0
    for record in thing:
        bases += len(record.seq)
    assert 1000 <= bases <= 1250
    os.remove('tests/asdf_R1.fasta')
    os.remove('tests/asdf_R2.fasta')


def test_kmerization():
    pair = ['tests/mashsippr/O157_R1.fastq.gz', 'tests/mashsippr/O157_R2.fastq.gz']
    generate_kmers(pair[0], pair[1], 'tests/counts.fasta', 31, 'tmp')
    expected_num_kmers = 23871
    thing = SeqIO.parse('tests/counts.fasta', 'fasta')
    i = 0
    for item in thing:
        i += 1
    assert i == expected_num_kmers
    os.remove('tests/counts.fasta')


def test_bam_parsing():
    fasta_ids = parse_bamfile('tests/subsample_0.bam', 31)
    assert len(fasta_ids) == 32


def test_present_database():
    assert check_db_presence('tests/fake_database.fasta') is True


def test_nonexistent_database():
    assert check_db_presence('tests/not_a_database.fasta') is False
