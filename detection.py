from accessoryFunctions.accessoryFunctions import printtime
from Bio.Blast.Applications import NcbiblastnCommandline
import os
import pysam
import gzip
import bz2
import subprocess
import glob


class ContamDetect:

    @staticmethod
    def parse_fastq_directory(fastq_folder):
        """
        Should be the first thing called on a ContamDetect object.
        :return: List of fastqpairs in nested array [[forward1, reverse1], [forward2, reverse2]] in fastq_pairs,
        list of single-ended files in fastq_singles
        """
        # Get a list of all fastq files. For some reason, having/not having the slash doesn't seem to matter on the
        # fastqfolder argument. These should be all the common extensions
        fastq_files = glob.glob(fastq_folder + "/*.fastq*")
        fastq_files += glob.glob(fastq_folder + "/*.fq*")
        fastq_pairs = list()
        fastq_singles = list()
        for name in fastq_files:
            # If forward and reverse reads are present, put them in a list of paired files.
            # May need to add support for other naming conventions too. Supports both _R1 and _1 type conventions.
            if "_R1" in name and os.path.isfile(name.replace("_R1", "_R2")):
                fastq_pairs.append([name, name.replace("_R1", "_R2")])
            # Other naming convention support.
            elif "_1" in name and os.path.isfile(name.replace("_1", "_2")):
                fastq_pairs.append([name, name.replace("_1", "_2")])
            # Assume that if we can't find a mate reads are single ended, and add them to the appropriate list.
            elif '_R2' not in name and '_2' not in name:
                fastq_singles.append(name)

        return fastq_pairs, fastq_singles

    def extract_rmlst_reads(self, fastq_pairs, fastq_singles):
        """
        Extracts rmlst reads and puts them in a folder.
        :param fastq_pairs: List of fastqpairs in nested array [[forward1, reverse1], [forward2, reverse2]]
        :param fastq_singles: List of fastq singles.
        :return: Zip, zilch, nada.
        """
        for pair in fastq_pairs:
            cmd = 'bbduk.sh ref={} in1={} in2={} outm={}' \
              ' outm2={}'.format(self.database, pair[0], pair[1], self.output_file + 'rmlsttmp/' + pair[0].split('/')[-1],
                                 self.output_file + 'rmlsttmp/' + pair[1].split('/')[-1])
            with open(self.output_file + 'tmp/junk.txt', 'w') as outjunk:
                try:  # This should give bbduk more than enough time to run, unless user's computer is super slow.
                    # Maybe adjust the value later.
                    subprocess.call(cmd, shell=True, stderr=outjunk, timeout=300)
                except subprocess.TimeoutExpired:
                    printtime(pair[0] + ' appears to be making BBDUK run forever. Killing...', self.start)
                    os.remove(self.output_file + 'rmlsttmp/' + pair[0].split('/')[-1])
                    os.remove(self.output_file + 'rmlsttmp/' + pair[1].split('/')[-1])

        for single in fastq_singles:
            cmd = 'bbduk.sh ref=database.fasta in={} outm={}' \
              ''.format(single, self.output_file + 'rmlsttmp/' + single.split('/')[-1])
            with open(self.output_file + 'tmp/junk.txt', 'w') as outjunk:
                try:  # This should give bbduk more than enough time to run, unless user's computer is super slow.
                    # Maybe adjust the value later.
                    subprocess.call(cmd, shell=True, stderr=outjunk, timeout=300)
                except subprocess.TimeoutExpired:
                    printtime(pair[0] + ' appears to be making BBDUK run forever. Killing...', self.start)
                    os.remove(self.output_file + 'rmlsttmp/' + single.split('/')[-1])

    def trim_fastqs(self, fastq_pairs, fastq_singles):
        """
        For each pair of fastqs in list passed, uses bbduk to trim those file, and puts them in a tmp directory.
        :param fastq_files: Fastq_pairs list generated by parse_fastq_directory.
        :return:
        """
        # Figure out where bbduk is so that we can use the adapter file.
        cmd = 'which bbduk.sh'
        bbduk_dir = subprocess.check_output(cmd.split()).decode('utf-8')
        bbduk_dir = bbduk_dir.split('/')[:-1]
        bbduk_dir = '/'.join(bbduk_dir)
        # Iterate through pairs, running bbduk and writing the trimmed output to the tmp folder for this run.
        for pair in fastq_pairs:
            out_forward = self.output_file + 'tmp/' + pair[0].split('/')[-1]
            out_reverse = self.output_file + 'tmp/' + pair[1].split('/')[-1]
            cmd = 'bbduk.sh in1={} in2={} out1={} out2={} qtrim=w trimq=20 k=25 minlength=50 forcetrimleft=15' \
                  ' ref={}/resources/adapters.fa overwrite hdist=1 tpe tbo threads={} '.format(pair[0], pair[1], out_forward,
                                                                                    out_reverse, bbduk_dir,
                                                                                    str(self.threads))
            with open(self.output_file + 'tmp/junk.txt', 'w') as outjunk:
                try:  # This should give bbduk more than enough time to run, unless user's computer is super slow.
                    # Maybe adjust the value later.
                    subprocess.call(cmd, shell=True, stderr=outjunk, timeout=300)
                except subprocess.TimeoutExpired:
                    printtime(pair[0] + ' appears to be making BBDUK run forever. Killing...', self.start)
                    os.remove(self.output_file + 'tmp/' + pair[0].split('/')[-1])
                    os.remove(self.output_file + 'tmp/' + pair[1].split('/')[-1])

        # Go through single reads, and run bbduk on them too.
        for single in fastq_singles:
            out_name = self.output_file + 'tmp/' + single.split('/')[-1]
            cmd = 'bbduk.sh in={} out={} qtrim=w trimq=20 k=25 minlength=50 forcetrimleft=15' \
                  ' ref={}/resources/adapters.fa hdist=1 tpe tbo threads={}'.format(single, out_name,
                                                                                    bbduk_dir, str(self.threads))
            with open(self.output_file + 'tmp/junk.txt', 'w') as outjunk:
                try:
                    subprocess.call(cmd, shell=True, stderr=outjunk, timeout=300)
                except subprocess.TimeoutExpired:
                    printtime(single + ' appears to be making BBDUK run forever. Killing...', self.start)
                    os.remove(self.output_file + 'tmp/' + single.split('/')[-1])

    def subsample_reads(self, fastq_pairs, fastq_singles):
        """
        Will subsample reads to approximately 20X coverage, which then means that we can (hopefully) manage to detect
        things better, and without false positives.
        :param fastq_pairs: List of pairs of fastqs.
        :param fastq_singles: List of single lonely fastqs
        :return:
        """
        for pair in fastq_pairs:
            with open(self.output_file + 'tmp/junk.txt', 'w') as outjunk:
                if '.gz' in pair[0]:
                    out1 = 'reads_R1.fastq.gz'
                    out2 = 'reads_R2.fastq.gz'
                elif '.bz2' in pair[0]:
                    out1 = 'reads_R1.fastq.bz2'
                    out2 = 'reads_R2.fastq.bz2'
                else:
                    out1 = 'reads_R1.fastq'
                    out2 = 'reads_R2.fastq'
                cmd = 'reformat.sh in1={} in2={} out1={} out2={} overwrite samplebasestarget=700000'.format(pair[0], pair[1],
                                                                                                  out1, out2)
                subprocess.call(cmd, shell=True, stderr=outjunk)
            os.rename(out1, pair[0])
            os.rename(out2, pair[1])

        for single in fastq_singles:
            with open(self.output_file + 'tmp/junk.txt', 'w') as outjunk:
                if '.gz' in single:
                    out = 'reads.fastq.gz'
                elif '.bz2' in single:
                    out = 'reads.fastq.bz2'
                else:
                    out = 'reads.fastq'
                cmd = 'reformat.sh in={} out={} samplebasestarget=700000'.format(single, out)
                subprocess.call(cmd, shell=True, stderr=outjunk)
            os.rename(out, single)

    def run_jellyfish(self, fastq, threads):
        """
        Runs jellyfish at kmer length of self.kmer_size.
        :param fastq: An array with forward reads at index 0 and reverse reads at index 1. Can also handle single reads,
        just input an array of length 1.
        :return: integer num_mers, which is number of kmers in the reads at that kmer size.
        """
        # Send files to check if they're compressed. If they are, create uncompressed version that jellyfish can handle.
        to_remove = list()
        to_use = list()
        for j in range(len(fastq)):
            uncompressed = ContamDetect.uncompress_file(fastq[j])
            if 'bz2' in fastq[j]:
                to_use.append(fastq[j].replace('bz2', ''))
                to_remove.append(fastq[j].replace('.bz2', ''))
            elif 'gz' in fastq[j]:
                to_use.append(fastq[j].replace('.gz', ''))
                to_remove.append(fastq[j].replace('.gz', ''))
            else:
                to_use.append(fastq[j])
        # Run jellyfish! Slightly different commands for single vs paired-end reads.
        if len(to_use) > 1:
            cmd = 'jellyfish count -m ' + str(self.kmer_size) + ' -s 100M --bf-size 100M -t ' + str(threads) + ' -C -F 2 ' +\
                  to_use[0] + ' ' + to_use[1] + ' -o ' + self.output_file + 'tmp/mer_counts.jf'
        else:
            cmd = 'jellyfish count -m ' + str(self.kmer_size) + ' -s 100M --bf-size 100M -t ' + str(threads) + ' -C -F 1 ' + \
                  to_use[0] + ' -o ' + self.output_file + 'tmp/mer_counts.jf'
        subprocess.call(cmd, shell=True)
        # If we had to uncompress files, remove the uncompressed versions.
        if uncompressed:
            for f in to_remove:
                try:
                    os.remove(f)
                except:# Needed in case the file has already been removed - figure out the specific error soon.
                    pass

    def write_mer_file(self, jf_file, fastq):
        """
        :param jf_file: .jf file created by jellyfish to be made into a fasta file
        :return: The number of unique kmers in said file.
        """
        # Dump the kmers into a fasta file.
        cmd = 'jellyfish dump {} > {}tmp/mer_sequences.fasta'.format(jf_file, self.output_file)
        subprocess.call(cmd, shell=True)
        # Read in the fasta file so we can assign a unique name to each kmer, otherwise things downstream will complain.
        f = open('{}tmp/mer_sequences.fasta'.format(self.output_file))
        fastas = f.readlines()
        f.close()
        out_solid = list()
        num_mers = 0
        # Try to figure out what coverage we have over the rMLST genes. This affects what cutoff we use to classify
        # a kmer as trustworthy. With more coverage, we need a higher cutoff.
        coverage = ContamDetect.estimate_coverage(35000, fastq)
        if coverage < 30:
            cutoff = 1
        elif coverage < 100:
            cutoff = 3
        elif coverage < 200:
            cutoff = 4
        else:
            cutoff = 5
        # Iterate through our kmer file, picking out kmers we've decided are trustworthy.
        for i in range(len(fastas)):
            if '>' in fastas[i]:
                if int(fastas[i].replace('>', '')) > cutoff:
                    num_mers += 1
                    out_solid.append(fastas[i].rstrip() + '_' + str(num_mers) + '\n' + fastas[i + 1])
        # Write out our solid kmers to file to be used later.
        f = open(self.output_file + 'tmp/mer_solid.fasta', 'w')
        f.write(''.join(out_solid))
        f.close()
        return num_mers

    def run_bbmap(self, pair, threads):
        """
        Runs bbmap on mer_sequences.fasta, against mer_sequences.fasta, outputting to test.sam. Important to set
        ambig=all so kmers don't just match with themselves. The parameter pair is expected to be an array with forward
        reads at index 0 and reverse at index 1. If you want to pass single-end reads, just need to give it an array of
        length 1.
        """
        # Align our mer sequences against themselves. This will let us find mers with a mismatch or two between them
        # that are indicative of multiple alleles of the same gene being present.
        cmd = 'bbmap.sh ref=' + self.output_file + 'tmp/mer_solid.fasta in=' + self.output_file + 'tmp/mer_solid.fasta ambig=all ' \
              'outm=' + self.output_file + 'tmp/' + pair[0].split('/')[-1] + '.sam overwrite subfilter=1 insfilter=0 ' \
                                                     'delfilter=0 indelfilter=0 nodisk threads=' + str(threads)
        with open(self.output_file + 'tmp/junk.txt', 'w') as outjunk:
            subprocess.call(cmd, shell=True, stderr=outjunk)

    @staticmethod
    def uncompress_file(filename):
        """
        If a file is gzipped or bzipped, creates an uncompressed copy of that file in the same folder
        :param filename: Path to file you want to uncompress
        :return: True if the file needed to be uncompressed, otherwise false.
        """
        uncompressed = False
        if ".gz" in filename:
            in_gz = gzip.open(filename, 'rb')
            out = open(filename.replace('.gz', ''), 'wb')
            out.write(in_gz.read())
            out.close()
            uncompressed = True
        elif ".bz2" in filename:
            in_bz2 = bz2.BZ2File(filename, 'rb')
            out = open(filename.replace('.bz2', ''), 'wb')
            out.write(in_bz2.read())
            out.close()
            uncompressed = True
        return uncompressed

    def make_db(self):
        db_files = ['.nhr', '.nin', '.nsq']
        db_present = True
        for db_file in db_files:
            if not os.path.isfile(self.database + db_file):
                db_present = False
        if not db_present:
            print('Making database!')
            cmd = 'makeblastdb -dbtype nucl -in ' + self.database
            with open(self.output_file + 'tmp/junk.txt', 'w') as outfile:
                subprocess.call(cmd, shell=True, stderr=outfile, stdout=outfile)

    def present_in_db(self, query_sequence):
        """
        Checks if a sequence is present in our rMLST database, as some overhangs on reads can be in repetitive regions
        that could cause false positives and should therfore be screened out.
        :param query_sequence: nucleotide sequence, as a string.
        :return: True if sequence is found in rMLST database, False if it isn't.
        """
        # Check if the db is there, and if not, make it.
        self.make_db()
        # Blast the sequence against our database.
        blastn = NcbiblastnCommandline(db=self.database, outfmt=6)
        stdout, stderr = blastn(stdin=query_sequence)
        # If there's any result, the sequence is present. No result means not present.
        if stdout:
            return True
        else:
            return False

    def read_samfile(self, num_mers, fastq):
        # TODO: This has become larger than intended. Maybe split into two methods since this does a lot more than just
        # samfile reading now.
        """
        :param num_mers: Number of unique kmers for the sample be looked at. Found by write_mer_file.
        :param fastq: Array with forward read filepath at index 0, reverse read filepath at index 1. Alternatively, name
        of single-end read file in array of length 1.
        Parse through the SAM file generated by bbmap to find how often contaminating alleles are present.
        Also calls methods from genome_size.py in order to estimate genome size (good for finding cross-species contam).
        Writes results to user-specified output file.
        """
        f = open(self.output_file + 'tmp/mer_solid.fasta')
        mers = f.readlines()
        f.close()
        # Now actually goes at an acceptable speed. Yay.
        mer_dict = dict()
        for i in range(0, len(mers), 2):
            key = mers[i].replace('>', '')
            key = key.replace('\n', '')
            mer_dict[key] = mers[i + 1]
        i = 0
        # Open up the alignment file for parsing.
        try:  # In the event no rmlst genes are present, this will skip over the sample.
            samfile = pysam.AlignmentFile(self.output_file + 'tmp/' + fastq[0].split('/')[-1] + '.sam', 'r')
            # samfile = pysam.AlignmentFile('test.sam', 'r')
            for match in samfile:
                # We're interested in full-length matches with one mismatch. This gets us that.
                # Well, not quite actually. You end up with the possibility of multiple single substitutions,
                # but that actually seems to improve sensitivity a fair bit while not impacting specificity. Huzzah.
                if "1X" in match.cigarstring and match.query_alignment_length == self.kmer_size:
                    query = match.query_name
                    reference = samfile.getrname(match.reference_id)
                    # query_kcount = float(query.split('_')[-1])
                    # ref_kcount = float(reference.split('_')[-1])
                    query_kcount = float(query.split('_')[0])
                    ref_kcount = float(reference.split('_')[0])
                    if query_kcount > ref_kcount:
                        # print(reference, query)
                        high = query_kcount
                        low = ref_kcount
                        if 0.01 < low/high < 0.7:
                            if self.present_in_db(mer_dict[reference]):  # TODO: Maybe multithread this one day, since it isn't particularly quick.
                                i += 1
                    else:
                        # print(query, reference)
                        low = query_kcount
                        high = ref_kcount
                        if 0.01 < low/high < 0.7:
                            if self.present_in_db(mer_dict[reference]):
                                i += 1
                    # Ratios that are very low are likely sequencing errors, and high ratios are likely multiple similar
                    # genes within a genome (looking at you, E. coli!)
            # See if we meet our contamination requirements - at least 1 high confidence multiple allele SNV, or
            # enough unique kmers that we almost certainly have multiple species contributing to the rMLST genes.
            if i > 1 or num_mers > 50000:
                contaminated = True
            else:
                contaminated = False
            # Get our output ready.
            outstr = fastq[0].split('/')[-1] + ',' + str(i) + ',' + str(num_mers) + ',' + str(contaminated) + '\n'
            # Append to the results file.
            f = open(self.output_file + '.csv', 'a+')
            f.write(outstr)
            f.close()
            # Should get tmp files cleaned up here so disk space doesn't get overwhelmed if running many samples.
            files = glob.glob(self.output_file + 'tmp/*.sam')
            for f in files:
                os.remove(f)
        except OSError:  # This happens if there are no rMLST genes at all in the sample and so we end up with an empty
            # input. There might be a more elegant way to handle this.
            pass

    @staticmethod
    def estimate_coverage(estimated_size, pair):
        """
        :param estimated_size: Estimated size of genome, in basepairs. Using rMLST genes, assume ~35000
        :param pair: Array with structure [path_to_forward_reads, path_to_reverse_reads].
        :return: Estimated coverage depth of genome, as an integer.
        """
        # Use some shell magic to find how many basepairs in forward fastq file - cat it into paste, which lets cut take
        # only the second column (which has the sequence), and then count the number of characters.
        if ".gz" in pair[0]:
            cmd = 'zcat ' + pair[0] + ' | paste - - - - | cut -f 2 | wc -c'
        elif ".bz2" in pair[0]:
            cmd = 'bzcat ' + pair[0] + ' | paste - - - - | cut -f 2 | wc -c'
        else:
            cmd = 'cat ' + pair[0] + ' | paste - - - - | cut -f 2 | wc -c'
        number_bp = int(subprocess.check_output(cmd, shell=True))
        # Multiply by length of array (2 if paired files, 1 if single ended).
        number_bp *= len(pair)
        return number_bp/estimated_size

    def __init__(self, args, start):
        self.fastq_folder = args.fastq_folder
        self.output_file = args.output_file
        self.threads = args.threads
        self.database = args.database
        self.kmer_size = 31
        self.classify = args.classify
        self.start = start
        if not os.path.isdir(self.output_file + 'tmp'):
            os.makedirs(self.output_file + 'tmp')
        if not os.path.isdir(self.output_file + 'rmlsttmp'):
            os.makedirs(self.output_file + 'rmlsttmp')
        f = open(self.output_file + '.csv', 'w')
        f.write('File,rMLSTContamSNVs,NumUniqueKmers,Contaminated\n')
        f.close()



