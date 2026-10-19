package more.attune.automotive;

import java.net.URI;
import java.net.URISyntaxException;
import java.util.Locale;

/** Exact scheme/host/port checks, including permission origins and redirected navigation. */
public final class OriginPolicy {
    private final URI origin;

    public OriginPolicy(String value, boolean debugLoopback) {
        URI candidate = parse(value);
        if (candidate == null || candidate.getRawQuery() != null || candidate.getRawFragment() != null
                || !(candidate.getRawPath().isEmpty() || "/".equals(candidate.getRawPath()))
                || !("https".equals(candidate.getScheme()) || (debugLoopback
                    && "http".equals(candidate.getScheme()) && isLoopback(candidate.getHost())))) {
            throw new IllegalArgumentException("An explicit HTTPS origin is required");
        }
        origin = candidate;
    }

    private static URI parse(String value) {
        try {
            URI uri = new URI(value);
            if (uri.getHost() == null || uri.getRawUserInfo() != null
                    || uri.getPort() < -1 || uri.getPort() > 65535 || uri.getPort() == 0
                    || !("https".equals(uri.getScheme()) || "http".equals(uri.getScheme()))) return null;
            return uri;
        } catch (URISyntaxException | NullPointerException error) { return null; }
    }

    public boolean contains(String value) {
        URI uri = parse(value);
        return uri != null && origin.getScheme().equals(uri.getScheme())
                && origin.getHost().equalsIgnoreCase(uri.getHost()) && port(origin) == port(uri);
    }

    public static boolean isHttps(String value) {
        URI uri = parse(value);
        return uri != null && "https".equals(uri.getScheme());
    }

    private static int port(URI uri) {
        return uri.getPort() == -1 ? ("https".equals(uri.getScheme()) ? 443 : 80) : uri.getPort();
    }

    private static boolean isLoopback(String host) {
        return "localhost".equals(host.toLowerCase(Locale.ROOT)) || "127.0.0.1".equals(host);
    }
}
