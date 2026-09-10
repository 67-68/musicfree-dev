#ifndef NNLS_CHROMA_BOOST_COMPAT_HPP
#define NNLS_CHROMA_BOOST_COMPAT_HPP

#include <cstddef>
#include <string>
#include <vector>

template <class CharT>
class char_separator {
public:
    char_separator(const char* dropped, const char* kept = "") {
        dropped_ = dropped ? dropped : "";
        kept_ = kept ? kept : "";
    }
    std::string dropped_;
    std::string kept_;
};

template <class SepT>
class tokenizer {
public:
    typedef std::vector<std::string>::const_iterator iterator;
    typedef std::vector<std::string>::const_iterator const_iterator;

    tokenizer(const std::string& input, const SepT& sep) {
        const std::string dropped = sep.dropped_;
        std::string cur;
        for (std::size_t i = 0; i < input.size(); ++i) {
            const char c = input[i];
            if (dropped.find(c) != std::string::npos) {
                if (!cur.empty()) { tokens_.push_back(cur); cur.clear(); }
            } else if (sep.kept_.find(c) != std::string::npos) {
                if (!cur.empty()) { tokens_.push_back(cur); cur.clear(); }
                tokens_.push_back(std::string(1, c));
            } else {
                cur.push_back(c);
            }
        }
        if (!cur.empty()) tokens_.push_back(cur);
    }

    iterator begin() const { return tokens_.begin(); }
    iterator end() const { return tokens_.end(); }

private:
    std::vector<std::string> tokens_;
};

#endif
