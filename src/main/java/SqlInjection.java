import java.sql.*;
import javax.servlet.http.HttpServletRequest;

public class SqlInjection {
    public static ResultSet doQuery(HttpServletRequest request, Connection connection) 
            throws SQLException {
        String customerName = request.getParameter("customerName");
        
        // Use PreparedStatement to prevent SQL injection
        String query = "SELECT account_balance FROM user_data WHERE user_name = ?";
        PreparedStatement preparedStatement = connection.prepareStatement(query);
        preparedStatement.setString(1, customerName);
        
        return preparedStatement.executeQuery();
    }
}
