class ArkUark < Formula
  include Language::Python::Virtualenv

  desc "Create and extract archives with progress and split volumes"
  homepage "https://github.com/CuiEM/ark-uark"
  url "https://github.com/CuiEM/ark-uark/archive/refs/tags/v0.1.0.tar.gz"
  sha256 "552c3422ffe709d5c1c1bd82455139e695095b47acb62cc82c7c4eb5bcfcf0aa"
  license "MIT"

  depends_on "python@3.14"
  depends_on "xz"
  depends_on "zstd"

  uses_from_macos "bzip2"
  uses_from_macos "gzip"

  def install
    virtualenv_install_with_resources
  end

  test do
    payload = (0...512).map { |index| "Homebrew #{index}: 中文档案\n" }.join
    (testpath/"source").mkpath
    (testpath/"source/中文.txt").write payload

    %w[tar tar.gz tar.bz2 tar.xz tar.zst zip gz bz2 xz zst].each do |format|
      single = %w[gz bz2 xz zst].include?(format)
      source = single ? testpath/"source/中文.txt" : testpath/"source"
      archive = testpath/"bundle.#{format}"
      destination = testpath/"restored-#{format}"

      system bin/"ark", source, "-o", archive, "-v", "128"
      assert_path_exists "#{archive}.part0001"
      system bin/"uark", "#{archive}.part0001", "-C", destination
      restored = single ? destination/"bundle" : destination/"source/中文.txt"
      assert_equal payload, restored.read
    end
  end
end
