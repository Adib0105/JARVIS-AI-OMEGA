param([Parameter(Mandatory=$true)][string]$Artifact, [Parameter(Mandatory=$true)][string]$CertificateThumbprint)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $Artifact -PathType Leaf)) { throw 'Artifact is missing.' }
$Certificate = Get-Item -LiteralPath ('Cert:\CurrentUser\My\' + $CertificateThumbprint)
if (-not $Certificate.HasPrivateKey -or $Certificate.NotAfter -lt (Get-Date)) { throw 'A valid owner-provisioned signing certificate with private key is required.' }
$Signature = Set-AuthenticodeSignature -FilePath $Artifact -Certificate $Certificate -HashAlgorithm SHA256 -TimestampServer 'http://timestamp.digicert.com'
if ($Signature.Status -ne 'Valid') { throw ('Signing did not verify: ' + $Signature.Status) }
$Verified = Get-AuthenticodeSignature -FilePath $Artifact
if ($Verified.Status -ne 'Valid' -or $Verified.SignerCertificate.Thumbprint -ne $CertificateThumbprint) { throw 'Artifact signature verification failed.' }
Write-Host 'Authenticode signature verified for the supplied certificate.'
