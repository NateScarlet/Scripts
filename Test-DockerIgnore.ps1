function Invoke-NativeCommand {
    $command, $arguments = $args
    & $command @arguments
    if (!$?) {
        Throw "exit code ${LastExitCode}: ${args}"
    }
}


# https://stackoverflow.com/a/40966234
$id = @'
FROM busybox
COPY . /build-context
WORKDIR /build-context
CMD find .
'@ | docker image build -q -f - .
if (!$?) {
    Throw "exit code ${LastExitCode}: docker image build -q -f - ."
}
Invoke-NativeCommand docker run --rm $id sh -c 'du -a | sort -g'
Invoke-NativeCommand docker rmi $id | Out-Null
