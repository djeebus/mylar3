# This script was taken almost entirely from Manders2600 Script with the use of the awesome ComicTagger.
# modified very slightly so Mylar just passes it the IssueID for it to do it's magic.


import os, errno
import sys
import re
import glob
import shlex
import platform
import shutil
import time
import zipfile
import subprocess
from subprocess import CalledProcessError, check_output
import mylar

from mylar import logger


def run(dirName, nzbName=None, issueid=None, comversion=None, manual=None, filename=None, module=None, manualmeta=False):
    if module is None:
        module = ''
    module += '[META-TAGGER]'

    logger.fdebug(module + ' dirName:' + dirName)

    # 2015-11-23: Recent CV API changes restrict the rate-limit to 1 api request / second.
    # ComicTagger has to be included now with the install as a timer had to be added to allow for the 1/second rule.
    comictagger_cmd = os.path.join(mylar.CMTAGGER_PATH, 'comictagger.py')
    logger.fdebug('ComicTagger Path location for internal comictagger.py set to : ' + comictagger_cmd)

    # Force mylar to use cmtagger_path = mylar.PROG_DIR to force the use of the included lib.

    logger.fdebug(module + ' Filename is : ' + filename)

    filepath = filename

    try:
        filename = os.path.split(filename)[1]   # just the filename itself
    except:
        logger.warn('Unable to detect filename within directory - I am aborting the tagging. You best check things out.')
        return "fail"

    #make use of temporary file location in order to post-process this to ensure that things don't get hammered when converting
    try:
        import tempfile
        new_folder = os.path.join(tempfile.mkdtemp(prefix='mylar_', dir=mylar.CACHE_DIR)) #prefix, suffix, dir
        new_filepath = os.path.join(new_folder, filename)
        if mylar.FILE_OPTS == 'copy' and manualmeta == False:
            shutil.copy(filepath, new_filepath)
        else:
            shutil.move(filepath, new_filepath)
        filepath = new_filepath  
    except:
        logger.warn(module + ' Unable to create temporary directory to perform meta-tagging. Processing without metatagging.')
        return "fail"

    ## Sets up other directories ##
    scriptname = os.path.basename(sys.argv[0])
    downloadpath = os.path.abspath(dirName)
    sabnzbdscriptpath = os.path.dirname(sys.argv[0])
    comicpath = new_folder

    logger.fdebug(module + ' Paths / Locations:')
    logger.fdebug(module + ' scriptname : ' + scriptname)
    logger.fdebug(module + ' downloadpath : ' + downloadpath)
    logger.fdebug(module + ' sabnzbdscriptpath : ' + sabnzbdscriptpath)
    logger.fdebug(module + ' comicpath : ' + comicpath)
    logger.fdebug(module + ' Running the ComicTagger Add-on for Mylar')


    ##set up default comictagger options here.
    #used for cbr - to - cbz conversion
    #depending on copy/move - eitehr we retain the rar or we don't.
    if mylar.FILE_OPTS == 'move':
        cbr2cbzoptions = ["-e", "--delete-rar"]
    else:
        cbr2cbzoptions = ["-e"]

    tagoptions = ["-s"]
    if mylar.CMTAG_VOLUME:
        if mylar.CMTAG_START_YEAR_AS_VOLUME:
            comversion = 'V' + str(comversion)
        else:
            if any([comversion is None, comversion == '', comversion == 'None']):
                comversion = '1'
            comversion = re.sub('[^0-9]', '', comversion).strip()
        cvers = 'volume=' + str(comversion)
    else:
        cvers = "volume="

    tagoptions.extend(["-m", cvers])

    try:
        ctversion = subprocess.check_output([sys.executable, comictagger_cmd, "--version"], stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        #logger.warn(module + "[WARNING] "command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))
        logger.warn(module + '[WARNING] Make sure that you are using the comictagger included with Mylar.')
        return "fail"

    ctend = ctversion.find('\n')
    ctcheck = re.sub("[^0-9]", "", ctversion[:ctend])
    ctcheck = re.sub('\.', '', ctcheck).strip()
    if int(ctcheck) >= int('1115'):  # (v1.1.15)
        if mylar.COMICVINE_API == mylar.DEFAULT_CVAPI:
            logger.fdebug(module + ' ' + ctversion[:ctend] + ' being used - no personal ComicVine API Key supplied. Take your chances.')
            use_cvapi = "False"
        else:
            logger.fdebug(module + ' ' + ctversion[:ctend] + ' being used - using personal ComicVine API key supplied via mylar.')
            use_cvapi = "True"
            tagoptions.extend(["--cv-api-key", mylar.COMICVINE_API])
    else:
        logger.fdebug(module + ' ' + ctversion[:ctend+1] + ' being used - personal ComicVine API key not supported in this version. Good luck.')
        use_cvapi = "False"

    i = 1
    tagcnt = 0

    if mylar.CT_TAG_CR:
        tagcnt = 1
        logger.fdebug(module + ' CR Tagging enabled.')

    if mylar.CT_TAG_CBL:
        if not mylar.CT_TAG_CR: i = 2  #set the tag to start at cbl and end without doing another tagging.
        tagcnt = 2
        logger.fdebug(module + ' CBL Tagging enabled.')

    if tagcnt == 0:
        logger.warn(module + ' You have metatagging enabled, but you have not selected the type(s) of metadata to write. Please fix and re-run manually')
        return "fail"

    #if it's a cbz file - check if no-overwrite existing tags is enabled / disabled in config.
    if filename.endswith('.cbz'):
        if mylar.CT_CBZ_OVERWRITE:
            logger.fdebug(module + ' Will modify existing tag blocks even if it exists.')
        else:
            logger.fdebug(module + ' Will NOT modify existing tag blocks even if they exist already.')
            tagoptions.extend(["--nooverwrite"])

    if issueid is None:
        tagoptions.extend(["-f", "-o"])
    else:
        tagoptions.extend(["-o", "--id", issueid])

    original_tagoptions = tagoptions
    og_tagtype = None
    initial_ctrun = True

    while (i <= tagcnt):
        if initial_ctrun:
            f_tagoptions = cbr2cbzoptions
            f_tagoptions.extend([filepath])
        else:
            if i == 1:
                tagtype = 'cr'  # CR meta-tagging cycle.
                tagdisp = 'ComicRack tagging'
            elif i == 2:
                tagtype = 'cbl'  # Cbl meta-tagging cycle
                tagdisp = 'Comicbooklover tagging'

            f_tagoptions = original_tagoptions

            if og_tagtype is not None:
                for index, item in enumerate(f_tagoptions):
                    if item == og_tagtype:
                        f_tagoptions[index] = tagtype
            else:
                f_tagoptions.extend(["--type", tagtype, filepath])

            og_tagtype = tagtype

            logger.info(module + ' ' + tagdisp + ' meta-tagging processing started.')

        currentScriptName = [sys.executable, comictagger_cmd]
        script_cmd = currentScriptName + f_tagoptions

        if initial_ctrun:
            logger.fdebug(module + ' Enabling ComicTagger script: ' + str(currentScriptName) + ' with options: ' + str(f_tagoptions))
            script_cmdlog = script_cmd

        else:
            logger.fdebug(module + ' Enabling ComicTagger script: ' + str(currentScriptName) + ' with options: ' + re.sub(f_tagoptions[f_tagoptions.index(mylar.COMICVINE_API)], 'REDACTED', str(f_tagoptions)))
            # generate a safe command line string to execute the script and provide all the parameters
            script_cmdlog = re.sub(f_tagoptions[f_tagoptions.index(mylar.COMICVINE_API)], 'REDACTED', str(script_cmd))
        
        logger.fdebug(module + ' Executing command: ' +str(script_cmdlog))
        logger.fdebug(module + ' Absolute path to script: ' +script_cmd[0])
        try:
            # use subprocess to run the command and capture output
            p = subprocess.Popen(script_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            out, err = p.communicate()
            #logger.info(out)
            #logger.info(err)
            if initial_ctrun and 'exported successfully' in out:
                logger.fdebug(module + '[COMIC-TAGGER] : ' +str(out))
                #Archive exported successfully to: X-Men v4 008 (2014) (Digital) (Nahga-Empire).cbz (Original deleted)
                tmpfilename = re.sub('Archive exported successfully to: ', '', out.rstrip())
                if mylar.FILE_OPTS == 'move':
                    tmpfilename = re.sub('\(Original deleted\)', '', tmpfilename).strip()
                tmpf = tmpfilename.decode('utf-8')
                filepath = os.path.join(comicpath, tmpf)
                if not os.path.isfile(filepath):
                    logger.fdebug(module + 'Trying utf-8 conversion.')
                    tmpf = tmpfilename.encode('utf-8')
                    filepath = os.path.join(comicpath, tmpf)
                    if not os.path.isfile(filepath):
                        logger.fdebug(module + 'Trying latin-1 conversion.')
                        tmpf = tmpfilename.encode('Latin-1')
                        filepath = os.path.join(comicpath, tmpf)

                logger.fdebug(module + '[COMIC-TAGGER][CBR-TO-CBZ] New filename: ' + filepath)
                initial_ctrun = False
            elif initial_ctrun and 'Archive is not a RAR' in out:
                initial_ctrun = False
            elif initial_ctrun:
                logger.warn(module + '[COMIC-TAGGER][CBR-TO-CBZ] Failed to convert cbr to cbz - check permissions on folder : ' + mylar.CACHE_DIR + ' and/or the location where Mylar is trying to tag the files from.')
                initial_ctrun = False
                return 'fail'
            elif 'Cannot find' in out:
                logger.warn(module + '[COMIC-TAGGER] Unable to locate file: ' + filename)
                file_error = 'file not found||' + filename
                return file_error
            elif 'not a comic archive!' in out:
                logger.warn(module + '[COMIC-TAGGER] Unable to locate file: ' + filename)
                file_error = 'file not found||' + filename
                return file_error
            else:
                logger.info(module + '[COMIC-TAGGER] Successfully wrote ' + tagdisp + ' [' + filepath + ']')
                i+=1
        except OSError, e:
            logger.warn(module + '[COMIC-TAGGER] Unable to run comictagger with the options provided: ' + re.sub(f_tagoptions[f_tagoptions.index(mylar.COMICVINE_API)], 'REDACTED', str(script_cmd)))
            return "fail"

        if mylar.CBR2CBZ_ONLY and initial_ctrun == False:
            break

    return filepath
