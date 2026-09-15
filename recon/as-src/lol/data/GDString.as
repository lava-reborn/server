class lol.data.GDString
{
   var string;
   function GDString(str)
   {
      this.string = str;
   }
   function toString()
   {
      return "@" + lol.server.XMLString.escape(this.string) + "@";
   }
}
