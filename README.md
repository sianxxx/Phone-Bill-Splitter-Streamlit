# Phone Bill Splitter with Streamlit

## Overview

The **Phone Bill Splitter** is a Python application built with Streamlit that helps users split their phone bill among multiple users. This tool is especially useful for roommates, families, or any group of people sharing a phone plan who want to keep track of individual expenses. **Currently, it only supports T-Mobile carrier bills.**

You can access the application [here](https://phonebillsplitter.streamlit.app/).


## Features

- **User-Friendly Interface**: Streamlit provides an easy-to-use interface for entering and displaying data.
- **Flexible Splitting**: Split bills based on usage or fixed amounts.[Equally divides voice plan costs among users while calculating phone and international call charges individually.]
- **Detailed Summaries**: View summaries of individual contributions and total expenses.
- **PDF Bill Parsing**: Upload a PDF of your T-Mobile bill and the app will automatically extract the necessary information for splitting.
- **Google Login**: Secure login using your Gmail account.

## Installation

1. **Clone the repository**:
    ```sh
    git clone https://github.com/dineshsayana/Phone-Bill-Splitter-Streamlit.git
    cd Phone-Bill-Splitter-Streamlit
    ```

2. **Create a virtual environment** (optional but recommended):
    ```sh
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```

3. **Install the required packages**:
    ```sh
    pip install -r requirements.txt
    ```

## Usage

1. **Run the Streamlit app**:
    ```sh
    streamlit run app.py
    ```

2. **Login Using Gmail**:
    - You will be prompted to log in using your Gmail account. Follow the on-screen instructions to authenticate.

3. **Upload Bill PDF**:
    - Click on the "Browse files" button to upload your T-Mobile bill PDF.

4. **Enter User Details**:
    - Add users you can save the contacts.

5. **View Results**:
    - The app will display the split amounts for each user based on the extracted information from the PDF.

## File Structure

- `app.py`: Main file to run the Streamlit application.
- `requirements.txt`: List of dependencies required for the project.
- `README.md`: Project documentation.

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository.
2. Create a new branch (`git checkout -b feature/new-feature`).
3. Commit your changes (`git commit -am 'Add new feature'`).
4. Push to the branch (`git push origin feature/new-feature`).
5. Create a new Pull Request.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more details.

## Acknowledgements

- [Streamlit](https://streamlit.io/) for providing an easy-to-use web app framework.
