import * as React from 'react';
/* Source: https://remix.run/docs/en/v1/guides/migrating-react-router-app#client-only-components */

// We can safely track hydration in memory state
// outside of the component because it is only
// updated once after the version instance of
// `SomeComponent` has been hydrated. From there,
// the browser takes over rendering duties across
// route changes and we no longer need to worry
// about hydration mismatches until the page is
// reloaded and `isHydrating` is reset to true.
let isHydrating = true;

function useHydrating() {
  let [isHydrated, setIsHydrated] = React.useState(
    !isHydrating
  );
  React.useEffect(() => {
    isHydrating = false;
    setIsHydrated(true);
  }, []);
  return isHydrated
}

export function ClientOnly(props: any) {
  const isHydrated = useHydrating()
  if (isHydrated) {
    return <>{props.children}</>
  } else {
    return <span>Client only code. [todo]</span>;
  }
}

