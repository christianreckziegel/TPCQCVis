import os
import subprocess

CODEDIR = os.environ['TPCQCVIS_DIR']
DATADIR = os.environ['TPCQCVIS_DATA']
REPORTDIR = os.environ['TPCQCVIS_REPORT']

if __name__ == "__main__":
        # Move reports
        move_command = f"python {CODEDIR}/TPCQCVis/tools/moveFiles.py -i /cave/alice-tpc-qc/data/ -o {REPORTDIR} -p '*.html'"
        subprocess.run(move_command, shell=True)
        # rsync
        sync_command = f"gpg -d -q ~/.myssh.gpg | sshpass rsync -hvrPt {REPORTDIR} lxplus:/eos/project-a/alice-tpc-qc/www/reports/"
        subprocess.run(sync_command, shell=True)
        # Update server
        update_command = "gpg -d -q ~/.myssh.gpg | sshpass ssh lxplus 'python /eos/project-a/alice-tpc-qc/www_resources/updateServer.py'"
        subprocess.run(update_command, shell=True)