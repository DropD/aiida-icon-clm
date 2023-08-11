export PMI_NO_FORK=1
export PMI_NO_PREINITIALIZE=1
export PMI_MMAP_SYNC_WAIT_TIME=300

set -e

source ./inputs.sh  # get YYYY, MM, MAX_PP, UTILS_BINDIR

# untar
tar -C gcm_data_compressed -xf gcm_data/ERAINT_${YYYY}_${MM}.tar

# unzip
COUNT_PP = 0
for FILE in $(ls -1 gcm_data/*)
do
  BASE_NAME = $(basename $FILE .ncz)
  nccopy -k 2 gcm_data_compressed/${BASE_NAME}.ncz outfiles/${BASE_NAME}.nc & (( COUNT_PP=COUNT_PP+1 ))
  if [[ $COUNT_PP -ge $MAX_PP ]]
  then
    COUNT_PP = 0
    wait
  fi
done
wait
rm -rf gcm_data_compressed

# ccaf2icaf
cd outfiles
COUNT_PP = 0
for FILE in $(ls -1)
do
  ${UTILS_BINDIR}/ccaf2icaf $FILE 1
  ncks -h -O -x -v W_SO_REL,T_SO,soil1,soil1_bnds $FILE $FILE
  if [[ $COUNT_PP -ge $MAX_PP ]]
  then
    COUNT_PP = 0
    wait
  fi
done
wait
