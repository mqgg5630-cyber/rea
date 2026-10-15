(() => {
  const blocked = {
    alert: () => undefined,
    confirm: () => false,
    prompt: () => null,
    print: () => undefined,
  }

  for (const [name, value] of Object.entries(blocked)) {
    for (const target of [Window.prototype, window]) {
      try {
        Object.defineProperty(target, name, {
          configurable: false,
          enumerable: true,
          writable: false,
          value,
        })
      } catch {}
    }
  }
})()
