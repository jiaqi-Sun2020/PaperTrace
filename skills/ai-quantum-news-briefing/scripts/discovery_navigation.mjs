// Type/syntax guard used in the generated CUA call, before any browser action.
// Full query/date/target evidence admission remains in Python's existing contract.
export function assertNavigation(request) {
  if (!request || request.version !== 1 || request.type !== 'navigation_url' ||
      typeof request.url !== 'string' || typeof request.query !== 'string') {
    throw new TypeError('navigation_url_object_required');
  }
  const url = new URL(request.url);
  const expected = new URL('https://www.google.com/search');
  expected.searchParams.set('q', request.query);
  if (url.href !== expected.href || url.username || url.password || url.hash ||
      !request.query.startsWith('(') || !/^\d{4}-\d{2}-\d{2}$/.test(request.coverage_date)) {
    throw new TypeError('invalid_navigation_url');
  }
  return url.href;
}

export async function navigateSource(tab, request) {
  const url = assertNavigation(request);
  if (!tab || typeof tab.goto !== 'function') throw new TypeError('existing_tab_required');
  return await tab.goto(url); // A rejection is never retried or redirected here.
}
