package jobs

import "sync"

// Hub is an in-process pub/sub. SSE listeners subscribe here so real-time
// works even when Redis pub/sub is down (queues can still work independently).
type Hub struct {
	mu     sync.RWMutex
	topics map[string]map[chan []byte]struct{}
}

func NewHub() *Hub {
	return &Hub{topics: make(map[string]map[chan []byte]struct{})}
}

// Subscribe returns a buffered channel and an unsubscribe function.
// Unsubscribe is safe to call more than once.
func (h *Hub) Subscribe(topic string) (<-chan []byte, func()) {
	ch := make(chan []byte, 32)
	h.mu.Lock()
	if h.topics[topic] == nil {
		h.topics[topic] = make(map[chan []byte]struct{})
	}
	h.topics[topic][ch] = struct{}{}
	h.mu.Unlock()

	var once sync.Once
	unsub := func() {
		once.Do(func() {
			h.mu.Lock()
			delete(h.topics[topic], ch)
			if len(h.topics[topic]) == 0 {
				delete(h.topics, topic)
			}
			h.mu.Unlock()
			close(ch)
		})
	}
	return ch, unsub
}

// Publish fans out to all local subscribers. Slow consumers drop the message
// rather than blocking the publisher.
func (h *Hub) Publish(topic string, payload []byte) {
	h.mu.RLock()
	subs := h.topics[topic]
	chans := make([]chan []byte, 0, len(subs))
	for ch := range subs {
		chans = append(chans, ch)
	}
	h.mu.RUnlock()
	for _, ch := range chans {
		select {
		case ch <- payload:
		default:
		}
	}
}
