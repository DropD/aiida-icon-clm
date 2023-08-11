#!/usr/local/bin/bash
export PMI_NO_FORK=1
export PMI_NO_PREINITIALIZE=1
export PMI_MMAP_SYNC_WAIT_TIME=300

set -e

source ./inputs.sh  # get YYYY, MM, MAX_PP, UTILS_BINDIR

mkdir gcm_data_compressed
mkdir outfiles

# untar
tar -C gcm_data_compressed -xf gcm_data/year${YYYY}/ERAINT_${YYYY}_${MM}.tar

# unzip
COUNT_PP=0
for FILE in $(ls -1 gcm_data_compressed/*)
do
  BASE_NAME=$(basename $FILE .ncz)
  nccopy -k 2 gcm_data_compressed/${BASE_NAME}.ncz outfiles/${BASE_NAME}.nc & (( COUNT_PP=COUNT_PP+1 ))
  if [[ $COUNT_PP -ge $MAX_PP ]]
  then
    COUNT_PP=0
    wait
  fi
done
wait
rm -rf gcm_data_compressed

# ccaf2icaf
pushd outfiles
COUNT_PP=0
for FILE in $(ls -1)
do
(
  ${UTILS_BINDIR}/ccaf2icaf $FILE 1
  ncks -h -O -x -v W_SO_REL,T_SO,soil1,soil1_bnds $FILE $FILE
)&
  if [[ $COUNT_PP -ge $MAX_PP ]]
  then
    COUNT_PP=0
    wait
  fi
done
wait

popd
ITYPE_CALENDAR=0 #hardcoded for now
CHECK_RESULT=$(${CFU_BINDIR}/cfu check_files ${CURRENT_DATE} ${NEXT_DATE} \
	$(printf %02d ${HINCBOUND}):00:00 ${GCM_PREFIX} ${GCM_PREFIX} .nc \
	outfiles T $ITYPE_CALENDAR)

exit $CHECK_RESULT
