using System.Text.Json;
using System.Text.RegularExpressions;

namespace PlanReader.ManifestBridge;

/// <summary>
/// Data-only, offline, fail-closed adapter for future Unity 6 native REVIEW previews.
/// It NEVER authenticates source bytes or promotes quantities, even if input claims verified.
/// </summary>
public static class Program
{
    private const int MaxInputBytes = 16 * 1024 * 1024;
    private const int MaxObjects = 20_000;
    private static readonly Regex Sha256 = new("^[0-9a-fA-F]{64}$",
        RegexOptions.Compiled | RegexOptions.CultureInvariant);

    public static int Main(string[] args)
    {
        try
        {
            if (args.Length != 1 || !File.Exists(args[0]))
                throw new InvalidDataException("Usage: PlanReader.ManifestBridge <local-scene.json>");
            var file = new FileInfo(args[0]);
            if (file.Length <= 0 || file.Length > MaxInputBytes)
                throw new InvalidDataException("Local scene exceeds the 16 MiB safety limit");
            using var stream = file.OpenRead();
            using var document = JsonDocument.Parse(stream,
                new JsonDocumentOptions { MaxDepth = 32, AllowTrailingCommas = false });
            var result = ValidateAndDowngrade(document.RootElement);
            Console.WriteLine(JsonSerializer.Serialize(result,
                new JsonSerializerOptions { PropertyNamingPolicy = JsonNamingPolicy.CamelCase }));
            return 0;
        }
        catch (Exception exception) when (exception is InvalidDataException
                                       or IOException or JsonException
                                       or UnauthorizedAccessException)
        {
            Console.Error.WriteLine("Local scene rejected: " + exception.Message);
            return 2;
        }
    }

    private static JsonElement Required(JsonElement obj, string key)
    {
        if (obj.ValueKind != JsonValueKind.Object || !obj.TryGetProperty(key, out var value))
            throw new InvalidDataException("Missing " + key);
        return value;
    }

    private static string String(JsonElement obj, string key)
    {
        var e = Required(obj, key);
        if (e.ValueKind != JsonValueKind.String)
            throw new InvalidDataException("Invalid string: " + key);
        var s = e.GetString();
        if (string.IsNullOrWhiteSpace(s) || s.Length > 256)
            throw new InvalidDataException("Invalid identity: " + key);
        return s;
    }

    private static void Literal(JsonElement obj, string key, JsonValueKind kind)
    {
        if (Required(obj, key).ValueKind != kind)
            throw new InvalidDataException("Required contract flag failed: " + key);
    }

    private static double Finite(JsonElement value)
    {
        if (value.ValueKind != JsonValueKind.Number ||
            !value.TryGetDouble(out var number) || !double.IsFinite(number))
            throw new InvalidDataException("Nonfinite or nonnumeric source geometry");
        return number;
    }

    private static double[] Point(JsonElement point, int count)
    {
        if (point.ValueKind != JsonValueKind.Array || point.GetArrayLength() != count)
            throw new InvalidDataException("Invalid model point");
        return point.EnumerateArray().Select(Finite).ToArray();
    }

    private static bool EqualString(JsonElement obj, string key, string expected) =>
        Required(obj, key).ValueKind == JsonValueKind.String &&
        Required(obj, key).GetString() == expected;

    public static object ValidateAndDowngrade(JsonElement root)
    {
        if (!EqualString(root, "schemaVersion", "1.0.0"))
            throw new InvalidDataException("Unsupported source scene schema");
        Literal(root, "readOnly", JsonValueKind.True);
        Literal(root, "commercialQuantityPublicationAllowed", JsonValueKind.False);
        if (root.TryGetProperty("sourceSurfaces", out var untrustedSurfaces) &&
            untrustedSurfaces.ValueKind != JsonValueKind.Null &&
            (untrustedSurfaces.ValueKind != JsonValueKind.Array ||
             untrustedSurfaces.GetArrayLength() != 0))
            throw new InvalidDataException("Local source surfaces require authenticated producer");

        var scope = Required(root, "scope");
        var workspaceId = String(scope, "workspaceId");
        var projectId = String(scope, "projectId");
        var documentId = String(scope, "documentId");
        var revisionId = String(scope, "revisionId");
        var snapshotId = String(scope, "snapshotId");
        var sourceSha = String(scope, "sourceSha256");
        if (!Sha256.IsMatch(sourceSha))
            throw new InvalidDataException("Invalid source SHA-256 scope");
        var rev = Required(scope, "modelRevision");
        if (rev.ValueKind != JsonValueKind.Number || !rev.TryGetInt32(out var modelRev) || modelRev < 0)
            throw new InvalidDataException("Invalid model revision");

        var coords = Required(root, "coordinateSystem");
        if (!EqualString(coords, "unit", "metres"))
            throw new InvalidDataException("Unsupported coordinate unit");
        Literal(coords, "sourceToModelTransform", JsonValueKind.Null);
        var origin = Point(Required(coords, "renderOrigin"), 3);

        var objects = Required(root, "objects");
        if (objects.ValueKind != JsonValueKind.Array || objects.GetArrayLength() > MaxObjects)
            throw new InvalidDataException("20,000 model object limit");
        var ids = new HashSet<string>(StringComparer.Ordinal);
        var walls = new List<object>();
        foreach (var item in objects.EnumerateArray())
        {
            var objectId = String(item, "objectId");
            if (!ids.Add(objectId))
                throw new InvalidDataException("Duplicate source object ID");
            var type = String(item, "objectType");
            _ = String(item, "objectRevision");
            _ = String(item, "authority");
            if (!EqualString(item, "renderState", "review") &&
                !EqualString(item, "renderState", "verified"))
                throw new InvalidDataException("Invalid input review state");
            Literal(item, "canEdit", JsonValueKind.False);
            if (Required(item, "quantityLinks").ValueKind != JsonValueKind.Array ||
                Required(item, "unresolvedIssues").ValueKind != JsonValueKind.Array ||
                Required(item, "source").ValueKind != JsonValueKind.Object ||
                Required(item, "dimensions").ValueKind != JsonValueKind.Object)
                throw new InvalidDataException("Incomplete object evidence contract");

            // Untrusted local fields can be displayed, never used as proof.
            var dims = Required(item, "dimensions");
            foreach (var dimension in dims.EnumerateObject()) _ = Finite(dimension.Value);
            var g = Required(item, "geometry");
            if (g.ValueKind == JsonValueKind.Null) continue;
            if (g.ValueKind != JsonValueKind.Object || type != "wall")
                throw new InvalidDataException("Unsupported geometry producer");
            var kind = String(g, "kind");
            if (kind != "wallFace" && kind != "wallLine")
                throw new InvalidDataException("Unsupported source geometry kind");
            var start = Point(Required(g, "start"), 2);
            var end = Point(Required(g, "end"), 2);
            if (start.SequenceEqual(end))
                throw new InvalidDataException("Degenerate source wall");
            double? height = null;
            if (kind == "wallFace")
            {
                height = Finite(Required(g, "heightM"));
                if (height <= 0) throw new InvalidDataException("Invalid wall-face height");
            }
            walls.Add(new
            {
                objectId,
                kind,
                start,
                end,
                heightM = height,
                renderState = "review",
                locallyAuthenticated = false,
                canEdit = false,
                commercialQuantityPublicationAllowed = false
            });
        }

        return new
        {
            schemaVersion = "1.0.0",
            sourceScope = new
            {
                workspaceId, projectId, documentId, revisionId, snapshotId,
                sourceSha256 = sourceSha.ToLowerInvariant(),
                modelRevision = modelRev
            },
            coordinateSystem = new { unit = "metres", renderOrigin = origin },
            inputObjectCount = ids.Count,
            walls,
            renderState = "review",
            localEvidenceTrusted = false,
            measurementAuthorized = false,
            commercialQuantityPublicationAllowed = false,
            canEdit = false,
            caveat = "UNTRUSTED LOCAL MANIFEST: preview only; never a source-backed measurement"
        };
    }
}
