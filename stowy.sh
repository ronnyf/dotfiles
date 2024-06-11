#!/usr/bin/env sh

target_file_name="target.stowy"
current=`pwd`

for entry in "${current}"/*; do
	target_path="${entry}/${target_file_name}"
	if [ -e "${target_path}" ]; then
		package=`basename ${entry}`
		echo "stowy package '${package}' >>> begin"

        source ${target_path}
        #echo "got: ${STOWY_TARGET}"

		if [ ! -d "${STOWY_TARGET}" ]; then
			mkdir_cmd="mkdir -p ${STOWY_TARGET}"
            eval "${mkdir_cmd}"
		fi

		cmd="stow -t "${STOWY_TARGET}" -v ${package} --dotfiles --ignore=^target\.stowy$ --ignore=\.DS_Store"
		#echo "cmd: ${cmd}"
		eval "${cmd}"

		echo "stowy package '${package}' <<< done" 
	fi
done

