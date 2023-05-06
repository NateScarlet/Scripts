export default function usePolling({
  update,
  scheduleNext = requestAnimationFrame,
}: {
  update: () => Promise<void> | void;
  scheduleNext?: (update: () => void) => void;
}) {
  let isCancelled = false;
  async function run() {
    if (isCancelled) {
      return;
    }
    await update();
    scheduleNext(run);
  }
  function dispose() {
    isCancelled = true;
  }

  run();

  return {
    dispose,
  };
}
