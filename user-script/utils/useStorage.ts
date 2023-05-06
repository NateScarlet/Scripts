export type StorageLike = Pick<Storage, "getItem" | "setItem" | "removeItem">;

export default function useStorage<T>(
  storage: StorageLike,
  key: string,
  defaultValue: T
): {
  dispose(): void;
  value: T;
} {
  const state = {
    value: defaultValue,
  };
  function read() {
    const value = storage.getItem(key);
    if (value != null) {
      try {
        state.value = JSON.parse(value);
      } catch {
        state.value = defaultValue;
      }
    }
  }
  function write() {
    if (state.value == null) {
      storage.removeItem(key);
    } else {
      storage.setItem(key, JSON.stringify(state.value));
    }
  }
  read();
  function onStorage(e: StorageEvent) {
    if (e.storageArea === storage && e.key === key) {
      read();
    }
  }
  window.addEventListener("storage", onStorage);
  function dispose() {
    window.removeEventListener("storage", onStorage);
  }

  return {
    dispose,
    get value() {
      return state.value;
    },
    set value(v: T) {
      state.value = v;
      write();
    },
  };
}
