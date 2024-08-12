#os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = "/home/michalis/Documents/Work/MELETI/inspection_client/env/lib/python3.12/site-packages/PyQt5/Qt/plugins"

if __name__ == '__main__':
    import os
    from dotenv import load_dotenv

    env_path = r'C:\Users\Public\ICLOCAL\.env'
    load_dotenv(dotenv_path=env_path)

    if not os.path.exists(os.getenv("INSPECTION_CLIENT_FOLDERS_PATH")):
        print('env not set up correctly')

    load_dotenv(dotenv_path=os.path.join(os.getenv("INSPECTION_CLIENT_FOLDERS_PATH"), '.env'))

    if os.getenv("INSPECTION_CLIENT_TEMP_IMAGE_SIZE") is None:
        print('env not set up correctly')

    print(int(os.getenv("INSPECTION_CLIENT_TEMP_IMAGE_SIZE")))

    from resources.log import LoggerSingleton
    import sys
    from PyQt5.QtWidgets import QApplication, QStackedWidget
    from pages.main_page import MainPage
    from pages.new_preset_page import NewPresetPage
    from pages.live_page import LivePage

    from resources.database import initialize_db
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(os.getenv("INSPECTION_CLIENT_FOLDERS_PATH"), 'project.log')),
            logging.StreamHandler()
        ]
    )
    initialize_db()
    LoggerSingleton().start_listener()  # Start the logging listener process
    app = QApplication(sys.argv)

    stacked_widget = QStackedWidget()
    
    main_page = MainPage(stacked_widget)
    new_preset_page = NewPresetPage(stacked_widget)
    live_page = LivePage(stacked_widget)

    stacked_widget.addWidget(main_page)
    stacked_widget.addWidget(new_preset_page)
    stacked_widget.addWidget(live_page)
    
    stacked_widget.setCurrentIndex(0)

    stacked_widget.setWindowTitle('Image Inspector')
    stacked_widget.setGeometry(100, 100, 800, 600)
    stacked_widget.show()

    sys.exit(app.exec_())
