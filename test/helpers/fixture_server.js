'use strict';

// A local stand-in for the outside world during tests: good and broken feeds,
// article pages for link checks, and a small imitation of the X API.
// Every source and account here is fictional.

const http = require('node:http');

const X_TOKEN = 'test-token';

function esc(text) {
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function rss(items, title) {
  const body = items
    .map(
      (item) => `
    <item>
      <title>${esc(item.title)}</title>
      <link>${esc(item.link)}</link>
      ${item.guid ? `<guid isPermaLink="false">${esc(item.guid)}</guid>` : ''}
      <pubDate>${item.pubDate || 'Sat, 26 Sep 2026 14:00:00 -0400'}</pubDate>
      ${item.creator ? `<dc:creator><![CDATA[${item.creator}]]></dc:creator>` : ''}
      ${(item.categories || []).map((c) => `<category><![CDATA[${c}]]></category>`).join('')}
      <description><![CDATA[${item.description || ''}]]></description>
      ${item.content ? `<content:encoded><![CDATA[${item.content}]]></content:encoded>` : ''}
    </item>`,
    )
    .join('');
  return `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:dc="http://purl.org/dc/elements/1.1/">
  <channel>
    <title>${esc(title)}</title>
    <link>https://example.test/</link>
    <description>Fixture feed</description>${body}
  </channel>
</rss>`;
}

function atom(entries, title) {
  const body = entries
    .map(
      (e) => `
  <entry>
    <author><name>${esc(e.author)}</name></author>
    <id>${esc(e.id)}</id>
    <link href="${esc(e.link)}" />
    <updated>${e.updated || '2026-09-26T18:00:00+00:00'}</updated>
    <title>${esc(e.title)}</title>
    <content type="html">${esc(e.html)}</content>
  </entry>`,
    )
    .join('');
  return `<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>${esc(title)}</title>
  <id>urn:fixture:${esc(title)}</id>
  <updated>2026-09-26T18:00:00+00:00</updated>${body}
</feed>`;
}

function buildFeeds(base) {
  return {
    '/news.xml': rss(
      [
        {
          title: 'Governor Moore signs budget as General Assembly adjourns',
          link: `${base}/articles/budget`,
          guid: 'ledger-1001',
          creator: 'Jane Reporter',
          categories: ['Government & Politics'],
          description: '<p>Gov. Wes Moore signed the state budget on Friday.</p>',
          content:
            '<p>Gov. Wes Moore signed the $67 billion state budget on Friday as lawmakers in the General Assembly wrapped up a tense session.</p><p>Senate leaders called it a compromise.</p>',
        },
        {
          title: 'Police arrest suspect in Hamilton carjacking',
          link: `${base}/articles/carjacking`,
          guid: 'ledger-1002',
          creator: 'Sam Beat',
          description: '<p>Baltimore police arrested a 19-year-old in Tuesday&#8217;s carjacking.</p>',
        },
        {
          title: 'School board weighs later start times for students',
          link: `${base}/articles/start-times`,
          guid: 'ledger-1003',
          description: '<p>The Baltimore County school board heard from teachers and parents.</p>',
        },
        {
          title: 'BGE customers face another rate increase this winter',
          link: `${base}/articles/bge-rates`,
          guid: 'ledger-1004',
          description: '<p>Utility bills are set to climb again, regulators said.</p>',
        },
        {
          title: 'Orioles walk off in extra innings',
          link: `${base}/articles/orioles`,
          guid: 'ledger-1005',
          description: '<p>The Orioles won 5-4 in the 11th inning at Camden Yards.</p>',
        },
        {
          title: 'Council members question police overtime',
          link: '/articles/relative-overtime',
          guid: 'ledger-1006',
          description: '<p>The city council pressed the police commissioner on overtime costs.</p>',
        },
        {
          title: 'Link-less mayor item',
          link: 'javascript:alert(1)',
          guid: 'ledger-1007',
          description: '<p>The mayor said something.</p>',
        },
        {
          title: 'County executive race tightens',
          link: `${base}/gone/exec-race`,
          guid: 'ledger-1008',
          description: '<p>The county executive race is close, a new poll shows.</p>',
        },
      ],
      'Chesapeake Ledger',
    ),
    '/commentary.xml': atom(
      [
        {
          author: '/u/crabcakefan',
          id: 't3_aaa111',
          link: `${base}/r/baltimore/comments/aaa111`,
          title: 'Water bill doubled and nobody at City Hall will explain why',
          html: '<p>My water bill doubled since spring. I called 311 twice. Nobody at City Hall will explain why rates keep climbing.</p>',
        },
        {
          author: '/u/hampden_hal',
          id: 't3_bbb222',
          link: `${base}/r/baltimore/comments/bbb222`,
          title: 'Police helicopter circling Hampden for an hour',
          html: '<p>Anyone know what happened? Police cars everywhere on 36th Street.</p>',
        },
        {
          author: '/u/snackdad',
          id: 't3_ccc333',
          link: `${base}/r/baltimore/comments/ccc333`,
          title: 'Best crab cakes near the harbor?',
          html: '<p>Visiting next week, want the real thing.</p>',
        },
      ],
      'r/testbaltimore',
    ),
    '/relief.xml': rss(
      [
        {
          title: 'Dog steals police officer’s hat during parade, refuses to give it back',
          link: `${base}/relief/hat-thief`,
          guid: 'pup-1',
          description: '<p>A golden retriever named Biscuit made off with an officer’s hat at the Hampden parade. Police say the investigation is ongoing and the suspect is a very good boy.</p>',
        },
        {
          title: 'Corgi meets snow for the first time',
          link: `${base}/relief/corgi-snow`,
          guid: 'pup-2',
          description: '<p>Forty-five seconds of pure joy.</p>',
        },
        {
          title: 'I told strangers their dog was famous and they believed me',
          link: `${base}/relief/famous-dog-prank`,
          guid: 'pup-3',
          description: '<p>Honestly the best reactions I have ever gotten. Half of them asked for an autograph from the dog.</p>',
        },
      ],
      'Happy Pups',
    ),
    '/dup.xml': rss(
      [
        {
          title: 'Moore signs budget (syndicated copy)',
          link: `${base}/articles/budget?utm_source=rss&utm_medium=feed#comments`,
          guid: 'wire-9001',
          description: '<p>Gov. Wes Moore signed the state budget.</p>',
        },
        {
          title: 'Teachers union endorses candidate for county executive',
          link: `${base}/articles/union-endorsement`,
          guid: 'wire-9002',
          description: '<p>The teachers union backed a candidate in the county executive race.</p>',
        },
        {
          title: 'Teachers union endorses candidate for county executive',
          link: `${base}/articles/union-endorsement`,
          guid: 'wire-9002',
          description: 'The same item twice in one feed.',
        },
      ],
      'Wire copy',
    ),
  };
}

// Latin-1 bytes whose charset is declared only in the XML declaration.
function latin1Feed(base) {
  const xml = `<?xml version="1.0" encoding="ISO-8859-1"?>
<rss version="2.0"><channel><title>Café Gazette</title><link>https://example.test/</link><description>x</description>
<item><title>Café owners protest property tax hike</title><link>${base}/articles/cafe-tax</link><guid>cafe-1</guid>
<description>Owners of the café say the tax is unaffordable.</description></item>
</channel></rss>`;
  return Buffer.from(xml, 'latin1');
}

// A small imitation of the X API v2 endpoints fetch_feeds.js uses.
const X_USERS = {
  testcampaign: { id: '501', username: 'TestCampaign', name: 'Test Campaign' },
  testdogs: { id: '502', username: 'TestDogs', name: 'Test Dogs' },
};

function xPosts(base) {
  return {
    501: [
      {
        id: '9003',
        created_at: '2026-09-26T16:00:00.000Z',
        text: 'Another win for Maryland families: we cut the ribbon on 500 affordable homes today. Details https://t.co/aaa https://t.co/pic',
        entities: {
          urls: [
            { url: 'https://t.co/aaa', expanded_url: `${base}/articles/affordable-homes`, display_url: 'example.test/homes' },
            { url: 'https://t.co/pic', expanded_url: 'https://x.com/TestCampaign/status/9003/photo/1', display_url: 'pic.x.com/xyz' },
          ],
        },
      },
      {
        id: '9002',
        created_at: '2026-09-25T16:00:00.000Z',
        text: 'My opponent wants to raise your taxes. I will cut them…',
        note_tweet: {
          text: 'My opponent wants to raise your taxes. I will cut them. Every family in Maryland deserves to keep more of their paycheck, and as governor that is exactly what I will fight for.',
        },
      },
    ],
    502: [
      {
        id: '8001',
        created_at: '2026-09-26T12:00:00.000Z',
        text: 'This is Waffles. He found the sprinkler and has decided it is his mortal enemy. 13/10 https://t.co/vid',
        entities: { urls: [{ url: 'https://t.co/vid', expanded_url: 'https://x.com/TestDogs/status/8001/video/1', display_url: 'pic.x.com/vid' }] },
      },
    ],
  };
}

/**
 * Starts the fixture server on a random port. Resolves to { base, close, hits }.
 * `hits` counts requests per path, e.g. to check that the X API received since_id.
 */
function startFixtureServer() {
  return new Promise((resolve) => {
    const hits = [];
    const sockets = new Set();
    let base;
    const server = http.createServer((req, res) => {
      const url = new URL(req.url, base);
      hits.push(`${url.pathname}${url.search}`);
      const feeds = buildFeeds(base);
      if (feeds[url.pathname]) {
        res.writeHead(200, { 'content-type': 'application/rss+xml; charset=utf-8' });
        return res.end(feeds[url.pathname]);
      }
      switch (url.pathname) {
        case '/latin1.xml':
          res.writeHead(200, { 'content-type': 'text/xml' });
          return res.end(latin1Feed(base));
        case '/redirect.xml':
          res.writeHead(301, { location: '/relief.xml' });
          return res.end();
        case '/missing.xml':
          res.writeHead(404, { 'content-type': 'text/plain' });
          return res.end('not found');
        case '/hang.xml':
          return; // never answers
        case '/stall.xml':
          res.writeHead(200, { 'content-type': 'application/rss+xml' });
          return res.write('<?xml version="1.0"?><rss version="2.0"><channel><title>stall</title>'); // never finishes
        case '/broken.xml':
          res.writeHead(200, { 'content-type': 'application/rss+xml' });
          return res.end('<?xml version="1.0"?><rss version="2.0"><channel><title>Broken</title><item><title>Unclosed</item></channel></rss>');
        case '/page.html':
          res.writeHead(200, { 'content-type': 'text/html' });
          return res.end('<!doctype html><html><body><h1>Not a feed</h1></body></html>');
        case '/huge.xml':
          res.writeHead(200, { 'content-type': 'application/rss+xml', 'content-length': String(50 * 1024 * 1024) });
          return res.end();
      }
      if (url.pathname.startsWith('/articles/') || url.pathname.startsWith('/relief/') || url.pathname.startsWith('/r/')) {
        res.writeHead(200, { 'content-type': 'text/html' });
        return res.end('<!doctype html><title>Story</title><p>Story text.</p>');
      }
      if (url.pathname.startsWith('/2/')) return xApi(req, res, url, base);
      res.writeHead(404, { 'content-type': 'text/plain' });
      res.end('not found');
    });
    server.on('connection', (socket) => {
      sockets.add(socket);
      socket.on('close', () => sockets.delete(socket));
    });
    server.listen(0, '127.0.0.1', () => {
      base = `http://127.0.0.1:${server.address().port}`;
      resolve({
        base,
        hits,
        close: () =>
          new Promise((done) => {
            for (const socket of sockets) socket.destroy();
            server.close(done);
          }),
      });
    });
  });
}

function xApi(req, res, url, base) {
  const json = (status, body) => {
    res.writeHead(status, { 'content-type': 'application/json' });
    res.end(JSON.stringify(body));
  };
  if (req.headers.authorization !== `Bearer ${X_TOKEN}`) return json(401, { title: 'Unauthorized', status: 401, detail: 'Unauthorized' });
  let match = /^\/2\/users\/by\/username\/(\w+)$/.exec(url.pathname);
  if (match) {
    const user = X_USERS[match[1].toLowerCase()];
    return user
      ? json(200, { data: user })
      : json(200, { errors: [{ title: 'Not Found Error', detail: `Could not find user with username: [${match[1]}].` }] });
  }
  match = /^\/2\/users\/(\d+)\/tweets$/.exec(url.pathname);
  if (match) {
    const sinceId = url.searchParams.get('since_id');
    const posts = (xPosts(base)[match[1]] || []).filter((p) => !sinceId || BigInt(p.id) > BigInt(sinceId));
    if (!posts.length) return json(200, { meta: { result_count: 0 } });
    return json(200, { data: posts, meta: { result_count: posts.length, newest_id: posts[0].id, oldest_id: posts[posts.length - 1].id } });
  }
  return json(404, { title: 'Not Found' });
}

module.exports = { startFixtureServer, X_TOKEN };
