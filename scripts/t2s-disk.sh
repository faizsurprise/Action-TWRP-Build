# Source this from the Android build directory.
check_disk_space() {
    local available
    df -h .
    available=$(df -Pk . | awk 'NR == 2 { print $4 }')
    # Reserve space before starting the phase. Actual demand depends on the checkout and build.
    if (( available < 8 * 1024 * 1024 )); then
        echo "::error::Less than 8 GiB free before $1. See the measured disk usage above."
        return 1
    fi
}

monitor_disk_space() {
    while sleep 60 >/dev/null 2>&1; do
        df -h .
    done &
    disk_monitor_pid=$!
    trap 'kill "$disk_monitor_pid" 2>/dev/null; df -h .' EXIT
}
