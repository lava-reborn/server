class lol.server.mess.CSM_Login extends lol.server.mess.CSMessage
{
   var _name;
   var addProp;
   function CSM_Login(hash)
   {
      super();
      this._name = "login";
      this.addProp("hash",hash);
   }
}
