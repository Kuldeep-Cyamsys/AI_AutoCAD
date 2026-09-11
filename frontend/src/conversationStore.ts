function database(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open("forge-cad", 1);
    request.onupgradeneeded = () => request.result.createObjectStore("sessions");
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

export async function loadSession<T>(): Promise<T | undefined> {
  const db = await database();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction("sessions", "readonly");
    const request = transaction.objectStore("sessions").get("current");
    transaction.oncomplete = () => { db.close(); resolve(request.result); };
    transaction.onabort = () => { db.close(); reject(transaction.error); };
  });
}

let pending = Promise.resolve();
export function saveSession(value: unknown): Promise<void> {
  pending = pending.catch(() => {}).then(async () => {
    const db = await database();
    return new Promise<void>((resolve, reject) => {
      const transaction = db.transaction("sessions", "readwrite");
      transaction.objectStore("sessions").put(value, "current");
      transaction.oncomplete = () => { db.close(); resolve(); };
      transaction.onabort = () => { db.close(); reject(transaction.error); };
    });
  });
  return pending;
}
