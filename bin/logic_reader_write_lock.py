# _______________________________________________________________________
# Imports

from contextlib import contextmanager
from threading  import Lock


# _______________________________________________________________________
# Class

class RWLock(object):
    """ RWLock class; this is meant to allow an object to be read from by
        multiple threads, but only written to by a single thread at a time. See:
        https://en.wikipedia.org/wiki/Readers%E2%80%93writer_lock
        Usage:
            from rwlock import RWLock
            my_obj_rwlock = RWLock()
            # When reading from my_obj:
            with my_obj_rwlock.r_locked():
                do_read_only_things_with(my_obj)
            # When writing to my_obj:
            with my_obj_rwlock.w_locked():
                mutate(my_obj)
    """

    def __init__(self):
        """
        Initializes the RWLock object.
        :return: None
        :rtype: None
        """

        self.w_lock = Lock()
        self.num_r_lock = Lock()
        self.num_r = 0

    # ___________________________________________________________________
    # Reading methods.

    def r_acquire(self):
        """
        Acquires a read lock.

        :return: None
        :rtype: None
        """
        self.num_r_lock.acquire()
        self.num_r += 1
        if self.num_r == 1:
            self.w_lock.acquire()
        self.num_r_lock.release()

    def r_release(self):
        """
        Releases a read lock.

        :return: None
        :rtype: None
        """
        assert self.num_r > 0
        self.num_r_lock.acquire()
        self.num_r -= 1
        if self.num_r == 0:
            self.w_lock.release()
        self.num_r_lock.release()

    @contextmanager
    def r_locked(self):
        """ This method is designed to be used via the `with` statement. """
        try:
            self.r_acquire()
            yield
        finally:
            self.r_release()

    # ___________________________________________________________________
    # Writing methods.

    def w_acquire(self):
        self.w_lock.acquire()

    def w_release(self):
        self.w_lock.release()

    @contextmanager
    def w_locked(self):
        """ This method is designed to be used via the `with` statement. """
        try:
            self.w_acquire()
            yield
        finally:
            self.w_release()


if __name__ == '__main__':
    
    import threading

    marker = RWLock()
    WEEKDAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    today = 0

    def calendar_reader(id_number):
        global today
        name = 'Reader-' + str(id_number)
        while today < len(WEEKDAYS)-1:
            # print(today)
            with marker.r_locked():
                print(name, 'sees that today is', WEEKDAYS[today])

    def calendar_writer(id_number):
        
        global today
        name = 'Writer-' + str(id_number)
        while today < len(WEEKDAYS)-1:
            with marker.w_locked():
                today = (today + 1) % 7
                print(name, 'updated date to ', WEEKDAYS[today])
            

    
    #for i in range(10):
        #threading.Thread(target=calendar_reader, args=(i,)).start()
    for i in range(2):
        threading.Thread(target=calendar_writer, args=(i,)).start()
    print('Done')